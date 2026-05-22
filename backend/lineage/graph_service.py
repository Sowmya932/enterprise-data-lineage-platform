"""
graph_service.py
----------------
LineageGraphService: recursive upstream/downstream lineage traversal
backed by PostgreSQL WITH RECURSIVE CTEs.

Public API
----------
    service = LineageGraphService()

    # Walk all tables that feed into 'sales_summary' (up to 10 hops)
    upstream = service.fetch_upstream_lineage(db, "sales_summary")

    # Walk all tables that depend on 'orders' (up to 10 hops)
    downstream = service.fetch_downstream_lineage(db, "orders")

    # Check whether adding orders â†’ sales_summary would create a cycle
    is_cycle = service.has_circular_dependency(db, "orders", "sales_summary")

    # Return the entire graph as nodes + edges (for visualisation)
    graph = service.fetch_full_dependency_graph(db)

Design notes
------------
* On PostgreSQL all recursive queries use WITH RECURSIVE CTEs for maximum
  performance.  A `visited_path` ARRAY guards against cycles and the
  configurable `max_depth` cap prevents runaway recursion on large graphs.
* On any other dialect (SQLite for tests, etc.) equivalent Python BFS
  implementations are used so no PostgreSQL instance is required for the
  unit-test suite.
* All methods propagate exceptions after logging so the API layer can
  return appropriate HTTP error responses.
"""

import logging
from collections import deque
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DEFAULT_MAX_DEPTH = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dialect(db: Session) -> str:
    """Return the lowercase SQLAlchemy dialect name ('postgresql', 'sqlite', â€¦)."""
    return db.get_bind().dialect.name


class LineageGraphService:
    """
    Recursive lineage graph queries.

    Uses PostgreSQL WITH RECURSIVE CTEs in production and a pure-Python BFS
    fallback on other dialects (SQLite used in the test suite).
    """

    # ------------------------------------------------------------------
    # Upstream lineage  (target â†’ sources)
    # ------------------------------------------------------------------

    def fetch_upstream_lineage(
        self,
        db: Session,
        table_name: str,
        max_depth: int = _DEFAULT_MAX_DEPTH,
    ) -> Dict:
        """
        Return all tables that feed (directly or transitively) into *table_name*.

        Uses PostgreSQL WITH RECURSIVE on PostgreSQL, Python BFS otherwise.
        """
        logger.info(
            "Fetching upstream lineage | table=%s max_depth=%d dialect=%s",
            table_name,
            max_depth,
            _dialect(db),
        )
        if _dialect(db) == "postgresql":
            return self._upstream_pg(db, table_name, max_depth)
        return self._upstream_python(db, table_name, max_depth)

    def _upstream_pg(self, db: Session, table_name: str, max_depth: int) -> Dict:
        """PostgreSQL WITH RECURSIVE upstream traversal."""
        try:
            sql = text(
                """
                WITH RECURSIVE upstream_chain AS (
                    SELECT
                        lr.source_table,
                        lr.target_table,
                        lr.column_name,
                        lr.source_column,
                        lr.dag_id,
                        1                            AS depth,
                        ARRAY[lr.source_table]       AS visited_path
                    FROM lineage_relationships lr
                    WHERE lr.target_table = :table_name

                    UNION ALL

                    SELECT
                        lr.source_table,
                        lr.target_table,
                        lr.column_name,
                        lr.source_column,
                        lr.dag_id,
                        uc.depth + 1,
                        uc.visited_path || lr.source_table
                    FROM lineage_relationships lr
                    JOIN upstream_chain uc ON lr.target_table = uc.source_table
                    WHERE uc.depth < :max_depth
                      AND NOT (lr.source_table = ANY(uc.visited_path))
                )
                SELECT source_table, target_table, column_name,
                       source_column, dag_id, depth
                FROM upstream_chain
                ORDER BY depth, source_table;
                """
            )
            rows = db.execute(
                sql, {"table_name": table_name, "max_depth": max_depth}
            ).fetchall()
            lineage_chain = [
                {
                    "source_table": r.source_table,
                    "target_table": r.target_table,
                    "column_name": r.column_name,
                    "source_column": r.source_column,
                    "dag_id": r.dag_id,
                    "depth": r.depth,
                }
                for r in rows
            ]
            return self._upstream_result(table_name, max_depth, lineage_chain)
        except Exception:
            logger.exception("PG upstream query failed | table=%s", table_name)
            raise

    def _upstream_python(self, db: Session, table_name: str, max_depth: int) -> Dict:
        """Python BFS upstream traversal (dialect-agnostic fallback)."""
        from backend.database.orm_models import LineageRelationship

        visited_edges: set = set()
        lineage_chain: List[Dict] = []
        queue: deque = deque([(table_name, 0)])
        visited_nodes: set = {table_name}

        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            edges = (
                db.query(LineageRelationship)
                .filter(LineageRelationship.target_table == current)
                .all()
            )
            for edge in edges:
                key = (edge.source_table, edge.target_table)
                if key not in visited_edges:
                    visited_edges.add(key)
                    lineage_chain.append(
                        {
                            "source_table": edge.source_table,
                            "target_table": edge.target_table,
                            "column_name": edge.column_name,
                            "source_column": edge.source_column,
                            "dag_id": edge.dag_id,
                            "depth": depth + 1,
                        }
                    )
                    if edge.source_table not in visited_nodes:
                        visited_nodes.add(edge.source_table)
                        queue.append((edge.source_table, depth + 1))

        lineage_chain.sort(key=lambda x: (x["depth"], x["source_table"]))
        return self._upstream_result(table_name, max_depth, lineage_chain)

    @staticmethod
    def _upstream_result(table_name: str, max_depth: int, chain: List[Dict]) -> Dict:
        upstream_tables = sorted({e["source_table"] for e in chain})
        logger.info(
            "Upstream complete | table=%s edges=%d unique_sources=%d",
            table_name, len(chain), len(upstream_tables),
        )
        return {
            "table": table_name,
            "direction": "upstream",
            "depth_limit": max_depth,
            "total_edges": len(chain),
            "upstream_tables": upstream_tables,
            "lineage_chain": chain,
        }

    # ------------------------------------------------------------------
    # Downstream lineage  (source â†’ targets)
    # ------------------------------------------------------------------

    def fetch_downstream_lineage(
        self,
        db: Session,
        table_name: str,
        max_depth: int = _DEFAULT_MAX_DEPTH,
    ) -> Dict:
        """
        Return all tables that depend (directly or transitively) on *table_name*.

        Uses PostgreSQL WITH RECURSIVE on PostgreSQL, Python BFS otherwise.
        """
        logger.info(
            "Fetching downstream lineage | table=%s max_depth=%d dialect=%s",
            table_name,
            max_depth,
            _dialect(db),
        )
        if _dialect(db) == "postgresql":
            return self._downstream_pg(db, table_name, max_depth)
        return self._downstream_python(db, table_name, max_depth)

    def _downstream_pg(self, db: Session, table_name: str, max_depth: int) -> Dict:
        """PostgreSQL WITH RECURSIVE downstream traversal."""
        try:
            sql = text(
                """
                WITH RECURSIVE downstream_chain AS (
                    SELECT
                        lr.source_table,
                        lr.target_table,
                        lr.column_name,
                        lr.source_column,
                        lr.dag_id,
                        1                            AS depth,
                        ARRAY[lr.target_table]       AS visited_path
                    FROM lineage_relationships lr
                    WHERE lr.source_table = :table_name

                    UNION ALL

                    SELECT
                        lr.source_table,
                        lr.target_table,
                        lr.column_name,
                        lr.source_column,
                        lr.dag_id,
                        dc.depth + 1,
                        dc.visited_path || lr.target_table
                    FROM lineage_relationships lr
                    JOIN downstream_chain dc ON lr.source_table = dc.target_table
                    WHERE dc.depth < :max_depth
                      AND NOT (lr.target_table = ANY(dc.visited_path))
                )
                SELECT source_table, target_table, column_name,
                       source_column, dag_id, depth
                FROM downstream_chain
                ORDER BY depth, target_table;
                """
            )
            rows = db.execute(
                sql, {"table_name": table_name, "max_depth": max_depth}
            ).fetchall()
            lineage_chain = [
                {
                    "source_table": r.source_table,
                    "target_table": r.target_table,
                    "column_name": r.column_name,
                    "source_column": r.source_column,
                    "dag_id": r.dag_id,
                    "depth": r.depth,
                }
                for r in rows
            ]
            return self._downstream_result(table_name, max_depth, lineage_chain)
        except Exception:
            logger.exception("PG downstream query failed | table=%s", table_name)
            raise

    def _downstream_python(self, db: Session, table_name: str, max_depth: int) -> Dict:
        """Python BFS downstream traversal (dialect-agnostic fallback)."""
        from backend.database.orm_models import LineageRelationship

        visited_edges: set = set()
        lineage_chain: List[Dict] = []
        queue: deque = deque([(table_name, 0)])
        visited_nodes: set = {table_name}

        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            edges = (
                db.query(LineageRelationship)
                .filter(LineageRelationship.source_table == current)
                .all()
            )
            for edge in edges:
                key = (edge.source_table, edge.target_table)
                if key not in visited_edges:
                    visited_edges.add(key)
                    lineage_chain.append(
                        {
                            "source_table": edge.source_table,
                            "target_table": edge.target_table,
                            "column_name": edge.column_name,
                            "source_column": edge.source_column,
                            "dag_id": edge.dag_id,
                            "depth": depth + 1,
                        }
                    )
                    if edge.target_table not in visited_nodes:
                        visited_nodes.add(edge.target_table)
                        queue.append((edge.target_table, depth + 1))

        lineage_chain.sort(key=lambda x: (x["depth"], x["target_table"]))
        return self._downstream_result(table_name, max_depth, lineage_chain)

    @staticmethod
    def _downstream_result(table_name: str, max_depth: int, chain: List[Dict]) -> Dict:
        downstream_tables = sorted({e["target_table"] for e in chain})
        logger.info(
            "Downstream complete | table=%s edges=%d unique_targets=%d",
            table_name, len(chain), len(downstream_tables),
        )
        return {
            "table": table_name,
            "direction": "downstream",
            "depth_limit": max_depth,
            "total_edges": len(chain),
            "downstream_tables": downstream_tables,
            "lineage_chain": chain,
        }

    # ------------------------------------------------------------------
    # Circular dependency detection
    # ------------------------------------------------------------------

    def has_circular_dependency(
        self,
        db: Session,
        source_table: str,
        target_table: str,
    ) -> bool:
        """
        Return True if adding source_table â†’ target_table would create a cycle.

        On PostgreSQL: WITH RECURSIVE CTE walking downstream from target_table.
        Fallback: Python DFS from target_table checking if source_table is reachable.
        """
        logger.debug(
            "Circular dependency check | %s â†’ %s", source_table, target_table
        )
        if _dialect(db) == "postgresql":
            return self._circular_pg(db, source_table, target_table)
        return self._circular_python(db, source_table, target_table)

    def _circular_pg(
        self, db: Session, source_table: str, target_table: str
    ) -> bool:
        """PostgreSQL WITH RECURSIVE cycle detection."""
        try:
            sql = text(
                """
                WITH RECURSIVE cycle_check AS (
                    SELECT
                        lr.source_table,
                        lr.target_table,
                        ARRAY[lr.source_table, lr.target_table] AS visited
                    FROM lineage_relationships lr
                    WHERE lr.source_table = :target_table

                    UNION ALL

                    SELECT
                        lr.source_table,
                        lr.target_table,
                        cc.visited || lr.target_table
                    FROM lineage_relationships lr
                    JOIN cycle_check cc ON lr.source_table = cc.target_table
                    WHERE NOT (lr.target_table = ANY(cc.visited))
                )
                SELECT COUNT(*) AS cycle_count
                FROM cycle_check
                WHERE target_table = :source_table;
                """
            )
            result = db.execute(
                sql,
                {"source_table": source_table, "target_table": target_table},
            ).scalar()
            is_circular = int(result or 0) > 0
        except Exception:
            logger.exception(
                "PG circular check failed | %s â†’ %s", source_table, target_table
            )
            raise

        if is_circular:
            logger.warning(
                "Circular dependency detected | %s â†’ %s would form a cycle",
                source_table,
                target_table,
            )
        return is_circular

    def _circular_python(
        self, db: Session, source_table: str, target_table: str
    ) -> bool:
        """Python DFS cycle detection (dialect-agnostic fallback)."""
        from backend.database.orm_models import LineageRelationship

        # Walk downstream from target_table; if we reach source_table â†’ cycle
        visited: set = set()
        stack: List[str] = [target_table]

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            edges = (
                db.query(LineageRelationship)
                .filter(LineageRelationship.source_table == current)
                .all()
            )
            for edge in edges:
                if edge.target_table == source_table:
                    logger.warning(
                        "Circular dependency detected (python) | %s â†’ %s",
                        source_table,
                        target_table,
                    )
                    return True
                stack.append(edge.target_table)
        return False

    # ------------------------------------------------------------------
    # Full dependency graph  (all nodes + edges)
    # ------------------------------------------------------------------

    def fetch_full_dependency_graph(self, db: Session) -> Dict:
        """
        Return the complete lineage graph as nodes (tables) and edges.

        Suitable for visualisation tools (D3, Graphviz, Cytoscape, etc.).
        """
        logger.info("Fetching full dependency graph")
        try:
            from backend.database.orm_models import LineageRelationship, TableRecord

            tables = db.query(TableRecord).order_by(TableRecord.name).all()
            edges = db.query(LineageRelationship).order_by(
                LineageRelationship.source_table,
                LineageRelationship.target_table,
            ).all()

            return {
                "nodes": [
                    {"id": t.id, "name": t.name, "schema_name": t.schema_name}
                    for t in tables
                ],
                "edges": [
                    {
                        "id": e.id,
                        "source": e.source_table,
                        "target": e.target_table,
                        "column_name": e.column_name,
                        "source_column": e.source_column,
                        "dag_id": e.dag_id,
                        "created_at": (
                            e.created_at.isoformat() if e.created_at else None
                        ),
                    }
                    for e in edges
                ],
            }
        except Exception:
            logger.exception("Failed to fetch full dependency graph")
            raise

    # ------------------------------------------------------------------
    # Column-level upstream traversal  (source_col ← target_col)
    # ------------------------------------------------------------------

    def fetch_column_upstream(
        self,
        db: Session,
        table_name: str,
        column_name: str,
        max_depth: int = _DEFAULT_MAX_DEPTH,
    ) -> Dict:
        """
        Return all column-level sources that feed into *table_name.column_name*.

        Uses PostgreSQL WITH RECURSIVE on PostgreSQL, Python BFS otherwise.
        """
        logger.info(
            "Fetching column upstream | table=%s column=%s max_depth=%d dialect=%s",
            table_name, column_name, max_depth, _dialect(db),
        )
        if _dialect(db) == "postgresql":
            return self._col_upstream_pg(db, table_name, column_name, max_depth)
        return self._col_upstream_python(db, table_name, column_name, max_depth)

    def _col_upstream_pg(
        self, db: Session, table_name: str, column_name: str, max_depth: int
    ) -> Dict:
        """PostgreSQL WITH RECURSIVE column-level upstream traversal."""
        try:
            sql = text(
                """
                WITH RECURSIVE col_upstream AS (
                    SELECT
                        cl.source_table,
                        cl.source_column,
                        cl.target_table,
                        cl.target_column,
                        cl.transformation,
                        cl.dag_id,
                        1                                                    AS depth,
                        ARRAY[cl.source_table || '.' || cl.source_column]    AS visited_path
                    FROM column_lineage cl
                    WHERE cl.target_table  = :table_name
                      AND cl.target_column = :column_name

                    UNION ALL

                    SELECT
                        cl.source_table,
                        cl.source_column,
                        cl.target_table,
                        cl.target_column,
                        cl.transformation,
                        cl.dag_id,
                        cu.depth + 1,
                        cu.visited_path || (cl.source_table || '.' || cl.source_column)
                    FROM column_lineage cl
                    JOIN col_upstream cu
                      ON cl.target_table  = cu.source_table
                     AND cl.target_column = cu.source_column
                    WHERE cu.depth < :max_depth
                      AND NOT (
                            (cl.source_table || '.' || cl.source_column) = ANY(cu.visited_path)
                          )
                )
                SELECT source_table, source_column, target_table, target_column,
                       transformation, dag_id, depth
                FROM col_upstream
                ORDER BY depth, source_table, source_column;
                """
            )
            rows = db.execute(
                sql,
                {"table_name": table_name, "column_name": column_name, "max_depth": max_depth},
            ).fetchall()
            chain = [
                {
                    "source_table": r.source_table,
                    "source_column": r.source_column,
                    "target_table": r.target_table,
                    "target_column": r.target_column,
                    "transformation": r.transformation,
                    "dag_id": r.dag_id,
                    "depth": r.depth,
                }
                for r in rows
            ]
            return self._col_upstream_result(table_name, column_name, max_depth, chain)
        except Exception:
            logger.exception(
                "PG column upstream query failed | table=%s column=%s",
                table_name, column_name,
            )
            raise

    def _col_upstream_python(
        self, db: Session, table_name: str, column_name: str, max_depth: int
    ) -> Dict:
        """Python BFS column-level upstream traversal (dialect-agnostic fallback)."""
        from backend.database.orm_models import ColumnLineage

        visited_edges: set = set()
        chain: List[Dict] = []
        queue: deque = deque([((table_name, column_name), 0)])
        visited_cols: set = {(table_name, column_name)}

        while queue:
            (cur_table, cur_col), depth = queue.popleft()
            if depth >= max_depth:
                continue
            edges = (
                db.query(ColumnLineage)
                .filter(
                    ColumnLineage.target_table == cur_table,
                    ColumnLineage.target_column == cur_col,
                )
                .all()
            )
            for e in edges:
                key = (e.source_table, e.source_column, e.target_table, e.target_column)
                if key not in visited_edges:
                    visited_edges.add(key)
                    chain.append(
                        {
                            "source_table": e.source_table,
                            "source_column": e.source_column,
                            "target_table": e.target_table,
                            "target_column": e.target_column,
                            "transformation": e.transformation,
                            "dag_id": e.dag_id,
                            "depth": depth + 1,
                        }
                    )
                    src_pair = (e.source_table, e.source_column)
                    if src_pair not in visited_cols:
                        visited_cols.add(src_pair)
                        queue.append((src_pair, depth + 1))

        chain.sort(key=lambda x: (x["depth"], x["source_table"], x["source_column"]))
        return self._col_upstream_result(table_name, column_name, max_depth, chain)

    @staticmethod
    def _col_upstream_result(
        table_name: str, column_name: str, max_depth: int, chain: List[Dict]
    ) -> Dict:
        upstream_cols = sorted(
            {f"{e['source_table']}.{e['source_column']}" for e in chain}
        )
        logger.info(
            "Column upstream complete | table=%s column=%s edges=%d unique_sources=%d",
            table_name, column_name, len(chain), len(upstream_cols),
        )
        return {
            "table": table_name,
            "column": column_name,
            "direction": "upstream",
            "depth_limit": max_depth,
            "total_edges": len(chain),
            "upstream_columns": upstream_cols,
            "lineage_chain": chain,
        }

    # ------------------------------------------------------------------
    # Column-level downstream traversal  (source_col → target_col)
    # ------------------------------------------------------------------

    def fetch_column_downstream(
        self,
        db: Session,
        table_name: str,
        column_name: str,
        max_depth: int = _DEFAULT_MAX_DEPTH,
    ) -> Dict:
        """
        Return all column-level targets that depend on *table_name.column_name*.

        Uses PostgreSQL WITH RECURSIVE on PostgreSQL, Python BFS otherwise.
        """
        logger.info(
            "Fetching column downstream | table=%s column=%s max_depth=%d dialect=%s",
            table_name, column_name, max_depth, _dialect(db),
        )
        if _dialect(db) == "postgresql":
            return self._col_downstream_pg(db, table_name, column_name, max_depth)
        return self._col_downstream_python(db, table_name, column_name, max_depth)

    def _col_downstream_pg(
        self, db: Session, table_name: str, column_name: str, max_depth: int
    ) -> Dict:
        """PostgreSQL WITH RECURSIVE column-level downstream traversal."""
        try:
            sql = text(
                """
                WITH RECURSIVE col_downstream AS (
                    SELECT
                        cl.source_table,
                        cl.source_column,
                        cl.target_table,
                        cl.target_column,
                        cl.transformation,
                        cl.dag_id,
                        1                                                    AS depth,
                        ARRAY[cl.target_table || '.' || cl.target_column]    AS visited_path
                    FROM column_lineage cl
                    WHERE cl.source_table  = :table_name
                      AND cl.source_column = :column_name

                    UNION ALL

                    SELECT
                        cl.source_table,
                        cl.source_column,
                        cl.target_table,
                        cl.target_column,
                        cl.transformation,
                        cl.dag_id,
                        cd.depth + 1,
                        cd.visited_path || (cl.target_table || '.' || cl.target_column)
                    FROM column_lineage cl
                    JOIN col_downstream cd
                      ON cl.source_table  = cd.target_table
                     AND cl.source_column = cd.target_column
                    WHERE cd.depth < :max_depth
                      AND NOT (
                            (cl.target_table || '.' || cl.target_column) = ANY(cd.visited_path)
                          )
                )
                SELECT source_table, source_column, target_table, target_column,
                       transformation, dag_id, depth
                FROM col_downstream
                ORDER BY depth, target_table, target_column;
                """
            )
            rows = db.execute(
                sql,
                {"table_name": table_name, "column_name": column_name, "max_depth": max_depth},
            ).fetchall()
            chain = [
                {
                    "source_table": r.source_table,
                    "source_column": r.source_column,
                    "target_table": r.target_table,
                    "target_column": r.target_column,
                    "transformation": r.transformation,
                    "dag_id": r.dag_id,
                    "depth": r.depth,
                }
                for r in rows
            ]
            return self._col_downstream_result(table_name, column_name, max_depth, chain)
        except Exception:
            logger.exception(
                "PG column downstream query failed | table=%s column=%s",
                table_name, column_name,
            )
            raise

    def _col_downstream_python(
        self, db: Session, table_name: str, column_name: str, max_depth: int
    ) -> Dict:
        """Python BFS column-level downstream traversal (dialect-agnostic fallback)."""
        from backend.database.orm_models import ColumnLineage

        visited_edges: set = set()
        chain: List[Dict] = []
        queue: deque = deque([((table_name, column_name), 0)])
        visited_cols: set = {(table_name, column_name)}

        while queue:
            (cur_table, cur_col), depth = queue.popleft()
            if depth >= max_depth:
                continue
            edges = (
                db.query(ColumnLineage)
                .filter(
                    ColumnLineage.source_table == cur_table,
                    ColumnLineage.source_column == cur_col,
                )
                .all()
            )
            for e in edges:
                key = (e.source_table, e.source_column, e.target_table, e.target_column)
                if key not in visited_edges:
                    visited_edges.add(key)
                    chain.append(
                        {
                            "source_table": e.source_table,
                            "source_column": e.source_column,
                            "target_table": e.target_table,
                            "target_column": e.target_column,
                            "transformation": e.transformation,
                            "dag_id": e.dag_id,
                            "depth": depth + 1,
                        }
                    )
                    tgt_pair = (e.target_table, e.target_column)
                    if tgt_pair not in visited_cols:
                        visited_cols.add(tgt_pair)
                        queue.append((tgt_pair, depth + 1))

        chain.sort(key=lambda x: (x["depth"], x["target_table"], x["target_column"]))
        return self._col_downstream_result(table_name, column_name, max_depth, chain)

    @staticmethod
    def _col_downstream_result(
        table_name: str, column_name: str, max_depth: int, chain: List[Dict]
    ) -> Dict:
        downstream_cols = sorted(
            {f"{e['target_table']}.{e['target_column']}" for e in chain}
        )
        logger.info(
            "Column downstream complete | table=%s column=%s edges=%d unique_targets=%d",
            table_name, column_name, len(chain), len(downstream_cols),
        )
        return {
            "table": table_name,
            "column": column_name,
            "direction": "downstream",
            "depth_limit": max_depth,
            "total_edges": len(chain),
            "downstream_columns": downstream_cols,
            "lineage_chain": chain,
        }



