"""
impact_service.py
-----------------
ImpactAnalysisService: downstream impact analysis starting from a table or
column that is about to change.

Answers five questions for a given change point:
    1. Which downstream *tables* are affected?
    2. Which downstream *columns* are affected?
    3. Which *DAGs* will be impacted?
    4. A combined impact report (all of the above + severity).
    5. Does the proposed change introduce a circular dependency?

Public API
----------
    svc = ImpactAnalysisService()

    # Full impact report for a table change
    report = svc.analyze_table_impact(db, "orders")

    # Full impact report for a column change (scoped)
    report = svc.analyze_column_impact(db, "orders", "amount")

    # Full impact report by column name only (global, all tables)
    report = svc.analyze_column_impact_by_name(db, "amount")

    # Individual helpers
    tables  = svc.get_affected_tables(db, "orders")
    columns = svc.get_affected_columns(db, "orders", "amount")
    dags    = svc.get_impacted_dags(db, "orders")

    # Guard before writing a new lineage edge
    is_cycle = svc.has_circular_dependency(db, "orders", "sales_summary")

Severity scale (based on unique affected downstream tables)
-----------------------------------------------------------
    NONE     – 0 affected tables
    LOW      – 1-5
    MEDIUM   – 6-15
    HIGH     – 16-30
    CRITICAL – 31+

Design notes
------------
* PostgreSQL: all multi-hop traversals use WITH RECURSIVE CTEs.
  cycle guards: visited_path ARRAY prevents revisiting nodes.
* Other dialects (SQLite for the test suite): equivalent Python BFS
  with visited-set cycle guards.
* max_depth defaults to 10 and can be overridden on every call.
* All methods propagate exceptions after logging so the API layer can
  return appropriate HTTP error responses.
"""

import logging
from collections import deque
from typing import Dict, List, Optional, Set

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DEFAULT_MAX_DEPTH = 10


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dialect(db: Session) -> str:
    """Return the lowercase SQLAlchemy dialect name ('postgresql', 'sqlite', …)."""
    return db.get_bind().dialect.name


def _severity(affected_table_count: int) -> str:
    """
    Classify overall impact severity based on unique downstream tables affected.

    NONE     – 0
    LOW      – 1-5
    MEDIUM   – 6-15
    HIGH     – 16-30
    CRITICAL – 31+
    """
    if affected_table_count == 0:
        return "NONE"
    if affected_table_count <= 5:
        return "LOW"
    if affected_table_count <= 15:
        return "MEDIUM"
    if affected_table_count <= 30:
        return "HIGH"
    return "CRITICAL"


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class ImpactAnalysisService:
    """
    Downstream impact analysis.

    Uses PostgreSQL WITH RECURSIVE CTEs in production and a pure-Python BFS
    fallback on other dialects (SQLite used in the test suite).
    """

    # ------------------------------------------------------------------
    # Affected tables
    # ------------------------------------------------------------------

    def get_affected_tables(
        self,
        db: Session,
        source_table: str,
        max_depth: int = _DEFAULT_MAX_DEPTH,
    ) -> Dict:
        """
        Return every table that is directly or transitively fed by *source_table*.

        Returns a dict with keys:
            source_table, affected_tables (sorted list), lineage_chain,
            total_edges, depth_limit.
        """
        logger.info(
            "Detecting affected tables | source=%s max_depth=%d dialect=%s",
            source_table,
            max_depth,
            _dialect(db),
        )
        if _dialect(db) == "postgresql":
            chain = self._downstream_chain_pg(db, source_table, max_depth)
        else:
            chain = self._downstream_chain_python(db, source_table, max_depth)

        affected = sorted({e["target_table"] for e in chain})
        logger.info(
            "Affected tables | source=%s count=%d", source_table, len(affected)
        )
        return {
            "source_table": source_table,
            "affected_tables": affected,
            "total_edges": len(chain),
            "depth_limit": max_depth,
            "lineage_chain": chain,
        }

    # ------------------------------------------------------------------
    # Affected columns
    # ------------------------------------------------------------------

    def get_affected_columns(
        self,
        db: Session,
        source_table: str,
        source_column: str,
        max_depth: int = _DEFAULT_MAX_DEPTH,
    ) -> Dict:
        """
        Return every downstream column derived (directly or transitively) from
        *source_table.source_column*.

        Returns a dict with keys:
            source_table, source_column, affected_columns (list of
            {table, column, transformation_type, depth}), total_hops,
            depth_limit.
        """
        logger.info(
            "Detecting affected columns | source=%s.%s max_depth=%d dialect=%s",
            source_table,
            source_column,
            max_depth,
            _dialect(db),
        )
        if _dialect(db) == "postgresql":
            chain = self._column_downstream_pg(
                db, source_table, source_column, max_depth
            )
        else:
            chain = self._column_downstream_python(
                db, source_table, source_column, max_depth
            )

        affected = [
            {
                "table": e["target_table"],
                "column": e["target_column"],
                "transformation_type": e["transformation_type"],
                "depth": e["depth"],
            }
            for e in chain
        ]
        logger.info(
            "Affected columns | source=%s.%s count=%d",
            source_table,
            source_column,
            len(affected),
        )
        return {
            "source_table": source_table,
            "source_column": source_column,
            "affected_columns": affected,
            "total_hops": len(chain),
            "depth_limit": max_depth,
        }

    # ------------------------------------------------------------------
    # Impacted DAGs
    # ------------------------------------------------------------------

    def get_impacted_dags(
        self,
        db: Session,
        source_table: str,
        max_depth: int = _DEFAULT_MAX_DEPTH,
    ) -> Dict:
        """
        Return every distinct DAG whose lineage edges touch *source_table* or
        any of its downstream tables.

        Returns a dict with keys:
            source_table, impacted_dags (sorted list), dag_details
            (list of {dag_id, affected_table, depth}).
        """
        logger.info(
            "Identifying impacted DAGs | source=%s max_depth=%d dialect=%s",
            source_table,
            max_depth,
            _dialect(db),
        )
        if _dialect(db) == "postgresql":
            chain = self._downstream_chain_pg(db, source_table, max_depth)
        else:
            chain = self._downstream_chain_python(db, source_table, max_depth)

        dag_details: List[Dict] = []
        seen: Set[tuple] = set()

        # Include direct edges from the source table itself
        dag_details += self._dag_details_for_table(db, source_table, depth=0)

        for edge in chain:
            key = (edge["dag_id"], edge["target_table"])
            if edge["dag_id"] and key not in seen:
                seen.add(key)
                dag_details.append(
                    {
                        "dag_id": edge["dag_id"],
                        "affected_table": edge["target_table"],
                        "depth": edge["depth"],
                    }
                )

        impacted_dags = sorted({d["dag_id"] for d in dag_details if d["dag_id"]})
        logger.info(
            "Impacted DAGs | source=%s count=%d", source_table, len(impacted_dags)
        )
        return {
            "source_table": source_table,
            "impacted_dags": impacted_dags,
            "dag_details": dag_details,
        }

    # ------------------------------------------------------------------
    # Full impact report – table
    # ------------------------------------------------------------------

    def analyze_table_impact(
        self,
        db: Session,
        source_table: str,
        max_depth: int = _DEFAULT_MAX_DEPTH,
    ) -> Dict:
        """
        Comprehensive downstream impact report for a *table-level* change.

        Returns a dict with keys:
            source_table, severity, affected_tables, impacted_dags,
            total_edges, depth_limit, lineage_chain, dag_details.
        """
        logger.info(
            "Analyzing table impact | source=%s max_depth=%d", source_table, max_depth
        )
        if _dialect(db) == "postgresql":
            chain = self._downstream_chain_pg(db, source_table, max_depth)
        else:
            chain = self._downstream_chain_python(db, source_table, max_depth)

        affected_tables = sorted({e["target_table"] for e in chain})

        dag_details: List[Dict] = []
        seen: Set[tuple] = set()
        dag_details += self._dag_details_for_table(db, source_table, depth=0)
        for edge in chain:
            key = (edge["dag_id"], edge["target_table"])
            if edge["dag_id"] and key not in seen:
                seen.add(key)
                dag_details.append(
                    {
                        "dag_id": edge["dag_id"],
                        "affected_table": edge["target_table"],
                        "depth": edge["depth"],
                    }
                )

        impacted_dags = sorted({d["dag_id"] for d in dag_details if d["dag_id"]})

        return {
            "source_table": source_table,
            "severity": _severity(len(affected_tables)),
            "affected_tables": affected_tables,
            "impacted_dags": impacted_dags,
            "total_edges": len(chain),
            "depth_limit": max_depth,
            "lineage_chain": chain,
            "dag_details": dag_details,
        }

    # ------------------------------------------------------------------
    # Full impact report – column
    # ------------------------------------------------------------------

    def analyze_column_impact(
        self,
        db: Session,
        source_table: str,
        source_column: str,
        max_depth: int = _DEFAULT_MAX_DEPTH,
    ) -> Dict:
        """
        Comprehensive downstream impact report for a *column-level* change.

        Returns a dict with keys:
            source_table, source_column, severity, affected_tables,
            affected_columns, impacted_dags, total_hops, depth_limit,
            dag_details.
        """
        logger.info(
            "Analyzing column impact | source=%s.%s max_depth=%d",
            source_table,
            source_column,
            max_depth,
        )
        if _dialect(db) == "postgresql":
            col_chain = self._column_downstream_pg(
                db, source_table, source_column, max_depth
            )
        else:
            col_chain = self._column_downstream_python(
                db, source_table, source_column, max_depth
            )

        affected_tables = sorted({e["target_table"] for e in col_chain})
        affected_columns = [
            {
                "table": e["target_table"],
                "column": e["target_column"],
                "transformation_type": e["transformation_type"],
                "depth": e["depth"],
            }
            for e in col_chain
        ]

        # Collect DAGs from the column-level chain
        dag_details: List[Dict] = []
        seen: Set[tuple] = set()
        dag_details += self._dag_details_for_table(db, source_table, depth=0)
        for edge in col_chain:
            key = (edge.get("dag_id"), edge["target_table"])
            if edge.get("dag_id") and key not in seen:
                seen.add(key)
                dag_details.append(
                    {
                        "dag_id": edge["dag_id"],
                        "affected_table": edge["target_table"],
                        "depth": edge["depth"],
                    }
                )

        impacted_dags = sorted({d["dag_id"] for d in dag_details if d["dag_id"]})

        return {
            "source_table": source_table,
            "source_column": source_column,
            "severity": _severity(len(affected_tables)),
            "affected_tables": affected_tables,
            "affected_columns": affected_columns,
            "impacted_dags": impacted_dags,
            "total_hops": len(col_chain),
            "depth_limit": max_depth,
            "dag_details": dag_details,
        }

    # ==================================================================
    # Private – table-level downstream traversal
    # ==================================================================

    def _downstream_chain_pg(
        self, db: Session, source_table: str, max_depth: int
    ) -> List[Dict]:
        """PostgreSQL WITH RECURSIVE downstream traversal over lineage_relationships."""
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
                        1                           AS depth,
                        ARRAY[lr.target_table]      AS visited_path
                    FROM lineage_relationships lr
                    WHERE lr.source_table = :source_table

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
                sql, {"source_table": source_table, "max_depth": max_depth}
            ).fetchall()
            return [
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
        except Exception:
            logger.exception(
                "PG downstream chain failed | source=%s", source_table
            )
            raise

    def _downstream_chain_python(
        self, db: Session, source_table: str, max_depth: int
    ) -> List[Dict]:
        """Python BFS downstream traversal (dialect-agnostic fallback)."""
        from backend.database.orm_models import LineageRelationship

        visited_edges: Set[tuple] = set()
        chain: List[Dict] = []
        queue: deque = deque([(source_table, 0)])
        visited_nodes: Set[str] = {source_table}

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
                    chain.append(
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

        chain.sort(key=lambda x: (x["depth"], x["target_table"]))
        return chain

    # ==================================================================
    # Private – column-level downstream traversal
    # ==================================================================

    def _column_downstream_pg(
        self,
        db: Session,
        source_table: str,
        source_column: str,
        max_depth: int,
    ) -> List[Dict]:
        """PostgreSQL WITH RECURSIVE downstream column traversal over column_lineage."""
        try:
            sql = text(
                """
                WITH RECURSIVE col_chain AS (
                    SELECT
                        cl.source_table,
                        cl.source_column,
                        cl.target_table,
                        cl.target_column,
                        cl.transformation_type,
                        cl.dag_id,
                        1                                           AS depth,
                        ARRAY[cl.target_table || '.' || cl.target_column]
                                                                    AS visited_path
                    FROM column_lineage cl
                    WHERE cl.source_table  = :source_table
                      AND cl.source_column = :source_column

                    UNION ALL

                    SELECT
                        cl.source_table,
                        cl.source_column,
                        cl.target_table,
                        cl.target_column,
                        cl.transformation_type,
                        cl.dag_id,
                        cc.depth + 1,
                        cc.visited_path || (cl.target_table || '.' || cl.target_column)
                    FROM column_lineage cl
                    JOIN col_chain cc
                      ON cl.source_table  = cc.target_table
                     AND cl.source_column = cc.target_column
                    WHERE cc.depth < :max_depth
                      AND NOT (
                            (cl.target_table || '.' || cl.target_column)
                            = ANY(cc.visited_path)
                          )
                )
                SELECT source_table, source_column, target_table, target_column,
                       transformation_type, dag_id, depth
                FROM col_chain
                ORDER BY depth, target_table, target_column;
                """
            )
            rows = db.execute(
                sql,
                {
                    "source_table": source_table,
                    "source_column": source_column,
                    "max_depth": max_depth,
                },
            ).fetchall()
            return [
                {
                    "source_table": r.source_table,
                    "source_column": r.source_column,
                    "target_table": r.target_table,
                    "target_column": r.target_column,
                    "transformation_type": r.transformation_type,
                    "dag_id": r.dag_id,
                    "depth": r.depth,
                }
                for r in rows
            ]
        except Exception:
            logger.exception(
                "PG column downstream failed | source=%s.%s",
                source_table,
                source_column,
            )
            raise

    def _column_downstream_python(
        self,
        db: Session,
        source_table: str,
        source_column: str,
        max_depth: int,
    ) -> List[Dict]:
        """Python BFS column-level downstream traversal (dialect-agnostic fallback)."""
        from backend.database.orm_models import ColumnLineage

        visited: Set[tuple] = set()
        chain: List[Dict] = []
        queue: deque = deque([(source_table, source_column, 0)])

        while queue:
            cur_table, cur_col, depth = queue.popleft()
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
            for edge in edges:
                key = (
                    edge.source_table,
                    edge.source_column,
                    edge.target_table,
                    edge.target_column,
                )
                if key not in visited:
                    visited.add(key)
                    chain.append(
                        {
                            "source_table": edge.source_table,
                            "source_column": edge.source_column,
                            "target_table": edge.target_table,
                            "target_column": edge.target_column,
                            "transformation_type": edge.transformation_type,
                            "dag_id": edge.dag_id,
                            "depth": depth + 1,
                        }
                    )
                    queue.append((edge.target_table, edge.target_column, depth + 1))

        chain.sort(key=lambda x: (x["depth"], x["target_table"], x["target_column"]))
        return chain

    # ==================================================================
    # Private – DAG detail helper
    # ==================================================================

    def _dag_details_for_table(
        self, db: Session, table_name: str, depth: int
    ) -> List[Dict]:
        """
        Return {dag_id, affected_table, depth} rows for lineage edges whose
        source_table is *table_name*.  Used to capture DAGs that directly
        read the changed table even before any downstream hop.
        """
        from backend.database.orm_models import LineageRelationship

        try:
            edges = (
                db.query(LineageRelationship.dag_id)
                .filter(
                    LineageRelationship.source_table == table_name,
                    LineageRelationship.dag_id.isnot(None),
                )
                .distinct()
                .all()
            )
            return [
                {"dag_id": row.dag_id, "affected_table": table_name, "depth": depth}
                for row in edges
                if row.dag_id
            ]
        except Exception:
            logger.exception(
                "DAG detail query failed | table=%s", table_name
            )
            raise

    # ==================================================================
    # Circular dependency detection
    # ==================================================================

    def has_circular_dependency(
        self,
        db: Session,
        source_table: str,
        target_table: str,
        max_depth: int = _DEFAULT_MAX_DEPTH,
    ) -> bool:
        """
        Return True if adding source_table → target_table would introduce a cycle.

        Logic: walk *downstream* from target_table; if source_table is reachable
        the proposed edge would close a loop.

        Uses PostgreSQL WITH RECURSIVE on PostgreSQL, Python DFS otherwise.
        """
        logger.debug(
            "Circular dependency check | %s → %s", source_table, target_table
        )
        if source_table == target_table:
            return True
        if _dialect(db) == "postgresql":
            return self._circular_pg(db, source_table, target_table)
        return self._circular_python(db, source_table, target_table, max_depth)

    def _circular_pg(self, db: Session, source_table: str, target_table: str) -> bool:
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
                SELECT COUNT(*) AS hit
                FROM cycle_check
                WHERE target_table = :source_table;
                """
            )
            result = db.execute(
                sql,
                {"source_table": source_table, "target_table": target_table},
            ).scalar()
            return int(result or 0) > 0
        except Exception:
            logger.exception(
                "PG circular check failed | %s → %s", source_table, target_table
            )
            raise

    def _circular_python(
        self,
        db: Session,
        source_table: str,
        target_table: str,
        max_depth: int,
    ) -> bool:
        """Python DFS cycle detection (dialect-agnostic fallback)."""
        chain = self._downstream_chain_python(db, target_table, max_depth)
        reachable = {e["target_table"] for e in chain}
        return source_table in reachable

    # ==================================================================
    # Global column impact (search by column name across all tables)
    # ==================================================================

    def analyze_column_impact_by_name(
        self,
        db: Session,
        column_name: str,
        max_depth: int = _DEFAULT_MAX_DEPTH,
    ) -> Dict:
        """
        Comprehensive downstream impact report for a column name searched
        globally across *all* source tables.

        Useful when the caller does not know (or does not care) which specific
        table the column originates from — every table that exposes a column
        named *column_name* becomes a seed for the traversal.

        Returns the same shape as analyze_column_impact, with source_table=None.
        """
        logger.info(
            "Analyzing global column impact | column=%s max_depth=%d dialect=%s",
            column_name,
            max_depth,
            _dialect(db),
        )
        if _dialect(db) == "postgresql":
            col_chain = self._column_downstream_by_name_pg(db, column_name, max_depth)
        else:
            col_chain = self._column_downstream_by_name_python(
                db, column_name, max_depth
            )

        affected_tables = sorted({e["target_table"] for e in col_chain})
        affected_columns = [
            {
                "table": e["target_table"],
                "column": e["target_column"],
                "transformation_type": e["transformation_type"],
                "depth": e["depth"],
            }
            for e in col_chain
        ]

        # Collect DAGs — seed from every distinct source_table in the chain
        dag_details: List[Dict] = []
        seen_dag: Set[tuple] = set()
        seed_tables: Set[str] = {e["source_table"] for e in col_chain}
        for tbl in seed_tables:
            for detail in self._dag_details_for_table(db, tbl, depth=0):
                key = (detail["dag_id"], detail["affected_table"])
                if key not in seen_dag:
                    seen_dag.add(key)
                    dag_details.append(detail)
        for edge in col_chain:
            key = (edge.get("dag_id"), edge["target_table"])
            if edge.get("dag_id") and key not in seen_dag:
                seen_dag.add(key)
                dag_details.append(
                    {
                        "dag_id": edge["dag_id"],
                        "affected_table": edge["target_table"],
                        "depth": edge["depth"],
                    }
                )

        impacted_dags = sorted({d["dag_id"] for d in dag_details if d["dag_id"]})
        logger.info(
            "Global column impact | column=%s affected_tables=%d affected_cols=%d dags=%d",
            column_name,
            len(affected_tables),
            len(affected_columns),
            len(impacted_dags),
        )
        return {
            "source_table": None,
            "source_column": column_name,
            "severity": _severity(len(affected_tables)),
            "affected_tables": affected_tables,
            "affected_columns": affected_columns,
            "impacted_dags": impacted_dags,
            "total_hops": len(col_chain),
            "depth_limit": max_depth,
            "dag_details": dag_details,
        }

    def _column_downstream_by_name_pg(
        self, db: Session, column_name: str, max_depth: int
    ) -> List[Dict]:
        """
        PostgreSQL WITH RECURSIVE global column downstream traversal.
        Seeds the CTE from every row in column_lineage where
        source_column = column_name (regardless of source_table).
        """
        try:
            sql = text(
                """
                WITH RECURSIVE col_chain AS (
                    SELECT
                        cl.source_table,
                        cl.source_column,
                        cl.target_table,
                        cl.target_column,
                        cl.transformation_type,
                        cl.dag_id,
                        1                                             AS depth,
                        ARRAY[cl.target_table || '.' || cl.target_column]
                                                                      AS visited_path
                    FROM column_lineage cl
                    WHERE cl.source_column = :column_name

                    UNION ALL

                    SELECT
                        cl.source_table,
                        cl.source_column,
                        cl.target_table,
                        cl.target_column,
                        cl.transformation_type,
                        cl.dag_id,
                        cc.depth + 1,
                        cc.visited_path || (cl.target_table || '.' || cl.target_column)
                    FROM column_lineage cl
                    JOIN col_chain cc
                      ON cl.source_table  = cc.target_table
                     AND cl.source_column = cc.target_column
                    WHERE cc.depth < :max_depth
                      AND NOT (
                            (cl.target_table || '.' || cl.target_column)
                            = ANY(cc.visited_path)
                          )
                )
                SELECT source_table, source_column, target_table, target_column,
                       transformation_type, dag_id, depth
                FROM col_chain
                ORDER BY depth, target_table, target_column;
                """
            )
            rows = db.execute(
                sql, {"column_name": column_name, "max_depth": max_depth}
            ).fetchall()
            return [
                {
                    "source_table": r.source_table,
                    "source_column": r.source_column,
                    "target_table": r.target_table,
                    "target_column": r.target_column,
                    "transformation_type": r.transformation_type,
                    "dag_id": r.dag_id,
                    "depth": r.depth,
                }
                for r in rows
            ]
        except Exception:
            logger.exception(
                "PG global column downstream failed | column=%s", column_name
            )
            raise

    def _column_downstream_by_name_python(
        self, db: Session, column_name: str, max_depth: int
    ) -> List[Dict]:
        """Python BFS global column downstream (dialect-agnostic fallback)."""
        from backend.database.orm_models import ColumnLineage

        # Seed: every (source_table, source_column) where source_column matches
        seeds = (
            db.query(ColumnLineage.source_table, ColumnLineage.source_column)
            .filter(ColumnLineage.source_column == column_name)
            .distinct()
            .all()
        )

        visited: Set[tuple] = set()
        chain: List[Dict] = []
        queue: deque = deque(
            [(row.source_table, row.source_column, 0) for row in seeds]
        )

        while queue:
            cur_table, cur_col, depth = queue.popleft()
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
            for edge in edges:
                key = (
                    edge.source_table,
                    edge.source_column,
                    edge.target_table,
                    edge.target_column,
                )
                if key not in visited:
                    visited.add(key)
                    chain.append(
                        {
                            "source_table": edge.source_table,
                            "source_column": edge.source_column,
                            "target_table": edge.target_table,
                            "target_column": edge.target_column,
                            "transformation_type": edge.transformation_type,
                            "dag_id": edge.dag_id,
                            "depth": depth + 1,
                        }
                    )
                    queue.append((edge.target_table, edge.target_column, depth + 1))

        chain.sort(key=lambda x: (x["depth"], x["target_table"], x["target_column"]))
        return chain
