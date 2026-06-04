"""
column_service.py
-----------------
ColumnLineageService: rich column-level lineage storage and traversal.

Supports saving edges parsed directly from SQL (INSERT/CREATE AS SELECT),
classifying each mapping as one of:

    DIRECT          – plain column copy / pass-through
    ALIAS           – column exposed under a different name via AS
    AGGREGATE_SUM   – SUM(col)
    AGGREGATE_COUNT – COUNT(col) / COUNT(*)
    AGGREGATE_AVG   – AVG(col)
    AGGREGATE_MAX   – MAX(col)
    AGGREGATE_MIN   – MIN(col)
    CASE_WHEN       – CASE WHEN … END expression
    DERIVED         – any other computed / mixed expression

Public API
----------
    svc = ColumnLineageService()

    # Parse SQL and bulk-save all column edges
    result = svc.save_from_sql(db, sql, dag_id="etl_pipeline")

    # Save a single explicit edge
    edge = svc.save_edge(db, source_table="orders", source_column="amount",
                         target_table="summary", target_column="total",
                         transformation="SUM(orders.amount)",
                         transformation_type="AGGREGATE_SUM", dag_id="etl")

    # Recursive traversal  (cross-table, by column name only)
    upstream   = svc.fetch_upstream(db, column_name="total_sales")
    downstream = svc.fetch_downstream(db, column_name="order_amount")

    # Stats grouped by transformation type
    summary = svc.transformation_summary(db)
"""

import logging
from collections import deque
from typing import Dict, List, Optional

import sqlglot
from sqlglot import exp, parse_one
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database.orm_models import ColumnLineage

logger = logging.getLogger(__name__)

_DEFAULT_MAX_DEPTH = 10

# ---------------------------------------------------------------------------
# Transformation type constants
# ---------------------------------------------------------------------------

DIRECT = "DIRECT"
ALIAS = "ALIAS"
AGG_SUM = "AGGREGATE_SUM"
AGG_COUNT = "AGGREGATE_COUNT"
AGG_AVG = "AGGREGATE_AVG"
AGG_MAX = "AGGREGATE_MAX"
AGG_MIN = "AGGREGATE_MIN"
CASE_WHEN = "CASE_WHEN"
DERIVED = "DERIVED"

_VALID_TYPES = {DIRECT, ALIAS, AGG_SUM, AGG_COUNT, AGG_AVG, AGG_MAX, AGG_MIN, CASE_WHEN, DERIVED}

_AGG_MAP: Dict[type, str] = {
    exp.Sum: AGG_SUM,
    exp.Count: AGG_COUNT,
    exp.Avg: AGG_AVG,
    exp.Max: AGG_MAX,
    exp.Min: AGG_MIN,
}

# sqlglot renamed/removed some aggregate classes across versions.
_average_expr = getattr(exp, "Average", None)
if _average_expr is not None:
    _AGG_MAP[_average_expr] = AGG_AVG

_ALL_AGG_TYPES = tuple(_AGG_MAP.keys())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dialect(db: Session) -> str:
    return db.get_bind().dialect.name


def _classify_expression(inner: exp.Expression, has_alias: bool) -> str:
    """Determine the transformation_type for a SELECT expression."""
    # CASE WHEN
    if inner.find(exp.Case):
        return CASE_WHEN

    # Aggregate functions
    for agg_cls, agg_type in _AGG_MAP.items():
        if inner.find(agg_cls):
            return agg_type

    # Plain column reference with alias → ALIAS
    if isinstance(inner, exp.Column) and has_alias:
        return ALIAS

    # Plain column reference without alias → DIRECT
    if isinstance(inner, exp.Column):
        return DIRECT

    # Everything else
    return DERIVED


def _resolve_aliases(parsed: exp.Expression) -> Dict[str, str]:
    """Build alias→real_table_name lookup from all FROM / JOIN tables."""
    mapping: Dict[str, str] = {}
    for tbl in parsed.find_all(exp.Table):
        if tbl.alias:
            real = f"{tbl.db}.{tbl.name}" if tbl.db else tbl.name
            mapping[tbl.alias] = real
    return mapping


def _source_tables_in_order(parsed: exp.Expression, alias_map: Dict[str, str]) -> List[str]:
    """Return canonical table names from FROM + JOINs, de-duplicated."""
    seen: List[str] = []
    for tbl in parsed.find_all(exp.Table):
        raw = f"{tbl.db}.{tbl.name}" if tbl.db else tbl.name
        canonical = alias_map.get(raw, raw)
        if canonical not in seen:
            seen.append(canonical)
    return seen


def _column_sources(
    inner: exp.Expression,
    alias_map: Dict[str, str],
    source_tables: List[str],
) -> List[tuple]:
    """
    Return list of (source_table, source_column) pairs referenced in *inner*.

    Handles:
      - Explicit table-qualified columns  (t.col)
      - Unqualified columns               (col)  – attributed to first source table
      - COUNT(*) and similar              – returns (first_table, "*")
    """
    col_refs = list(inner.find_all(exp.Column))
    if not col_refs and isinstance(inner, exp.Column):
        col_refs = [inner]

    if not col_refs:
        fallback = source_tables[0] if source_tables else "unknown"
        return [(fallback, "*")]

    result: List[tuple] = []
    for col in col_refs:
        if col.table:
            tbl = alias_map.get(col.table, col.table)
        else:
            tbl = source_tables[0] if len(source_tables) == 1 else "unknown"
        pair = (tbl, col.name)
        if pair not in result:
            result.append(pair)
    return result


def _get_target_table(parsed: exp.Expression) -> Optional[str]:
    """Extract the write-target table from INSERT INTO / CREATE TABLE AS."""
    if isinstance(parsed, (exp.Insert, exp.Create, exp.Update, exp.Merge)):
        tbl = parsed.find(exp.Table)
        if tbl:
            return f"{tbl.db}.{tbl.name}" if tbl.db else tbl.name
    return None


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class ColumnLineageService:
    """
    Saves and traverses column-level lineage stored in the ``column_lineage``
    PostgreSQL table.

    All write methods are idempotent – duplicate edges are silently skipped.
    """

    # ------------------------------------------------------------------
    # Parse SQL → bulk save
    # ------------------------------------------------------------------

    def save_from_sql(
        self,
        db: Session,
        sql: str,
        *,
        dialect: str = "postgres",
        dag_id: Optional[str] = None,
    ) -> Dict:
        """
        Parse *sql* and persist every column-level lineage edge found.

        Supports:
          - Direct column copies (DIRECT)
          - Renamed columns via AS  (ALIAS)
          - SUM / COUNT / AVG / MAX / MIN aggregates
          - CASE WHEN expressions
          - Arbitrary derived / computed columns  (DERIVED)

        Returns
        -------
        {
          "target_table": str | None,
          "edges_saved": int,
          "edges_skipped": int,          # duplicates
          "edges": [ {edge dict}, ... ]
        }
        """
        logger.info("save_from_sql | dag=%s | sql_len=%d", dag_id, len(sql))
        try:
            parsed = parse_one(sql, dialect=dialect)
        except Exception as e:
            logger.warning("SQL parse error: %s", e)
            return {"target_table": None, "edges_saved": 0, "edges_skipped": 0, "edges": [], "error": str(e)}

        target_table = _get_target_table(parsed)
        if not target_table:
            return {
                "target_table": None,
                "edges_saved": 0,
                "edges_skipped": 0,
                "edges": [],
                "error": "No INSERT INTO / CREATE TABLE AS target found in SQL.",
            }

        select = parsed if isinstance(parsed, exp.Select) else parsed.find(exp.Select)
        if select is None:
            return {
                "target_table": target_table,
                "edges_saved": 0,
                "edges_skipped": 0,
                "edges": [],
                "error": "No SELECT clause found.",
            }

        alias_map = _resolve_aliases(parsed)
        source_tables = _source_tables_in_order(parsed, alias_map)

        edges_saved = 0
        edges_skipped = 0
        saved_edges: List[Dict] = []

        for sel in select.expressions:
            output_alias = sel.alias if sel.alias else None
            inner = sel.this if isinstance(sel, exp.Alias) else sel

            # Output column name
            if output_alias:
                target_col = output_alias
            elif isinstance(inner, exp.Column):
                target_col = inner.name
            elif isinstance(inner, exp.Star):
                target_col = "*"
            else:
                target_col = str(inner)[:128]  # truncate very long expressions

            transformation_type = _classify_expression(inner, has_alias=bool(output_alias))
            transformation_expr = str(inner)

            src_pairs = _column_sources(inner, alias_map, source_tables)

            for src_table, src_col in src_pairs:
                saved = self._upsert_edge(
                    db,
                    source_table=src_table,
                    source_column=src_col,
                    target_table=target_table,
                    target_column=target_col,
                    transformation=transformation_expr,
                    transformation_type=transformation_type,
                    dag_id=dag_id,
                )
                if saved:
                    edges_saved += 1
                    saved_edges.append(saved)
                else:
                    edges_skipped += 1

        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Commit failed in save_from_sql")
            raise

        logger.info(
            "save_from_sql complete | target=%s saved=%d skipped=%d",
            target_table, edges_saved, edges_skipped,
        )
        return {
            "target_table": target_table,
            "edges_saved": edges_saved,
            "edges_skipped": edges_skipped,
            "edges": saved_edges,
        }

    # ------------------------------------------------------------------
    # Save a single explicit edge
    # ------------------------------------------------------------------

    def save_edge(
        self,
        db: Session,
        *,
        source_table: str,
        source_column: str,
        target_table: str,
        target_column: str,
        transformation: Optional[str] = None,
        transformation_type: str = DIRECT,
        dag_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Persist one column-level edge and commit.

        Returns the saved edge dict, or None if it already existed (idempotent).
        """
        if transformation_type not in _VALID_TYPES:
            raise ValueError(
                f"Invalid transformation_type '{transformation_type}'. "
                f"Valid values: {sorted(_VALID_TYPES)}"
            )
        saved = self._upsert_edge(
            db,
            source_table=source_table,
            source_column=source_column,
            target_table=target_table,
            target_column=target_column,
            transformation=transformation,
            transformation_type=transformation_type,
            dag_id=dag_id,
        )
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        return saved

    def _upsert_edge(
        self,
        db: Session,
        *,
        source_table: str,
        source_column: str,
        target_table: str,
        target_column: str,
        transformation: Optional[str],
        transformation_type: str,
        dag_id: Optional[str],
    ) -> Optional[Dict]:
        """
        Add a ColumnLineage row to the session (no commit).

        Returns the to_dict() on success, None if the edge already exists.
        Uses a savepoint to survive IntegrityError without aborting the
        outer transaction.
        """
        existing = (
            db.query(ColumnLineage)
            .filter(
                ColumnLineage.source_table == source_table,
                ColumnLineage.source_column == source_column,
                ColumnLineage.target_table == target_table,
                ColumnLineage.target_column == target_column,
            )
            .first()
        )
        if existing:
            return None

        edge = ColumnLineage(
            source_table=source_table,
            source_column=source_column,
            target_table=target_table,
            target_column=target_column,
            transformation=transformation,
            transformation_type=transformation_type,
            dag_id=dag_id,
        )
        db.add(edge)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            return None
        return edge.to_dict()

    # ------------------------------------------------------------------
    # Cross-table upstream (by column name only)
    # ------------------------------------------------------------------

    def fetch_upstream(
        self,
        db: Session,
        column_name: str,
        max_depth: int = _DEFAULT_MAX_DEPTH,
    ) -> Dict:
        """
        Return all column-level sources that feed into any column named
        *column_name* (across all tables).

        PostgreSQL: WITH RECURSIVE CTE on column_lineage.
        Other dialects: Python BFS fallback.
        """
        logger.info(
            "fetch_upstream | column=%s max_depth=%d dialect=%s",
            column_name, max_depth, _dialect(db),
        )
        if _dialect(db) == "postgresql":
            return self._upstream_pg(db, column_name, max_depth)
        return self._upstream_python(db, column_name, max_depth)

    def _upstream_pg(self, db: Session, column_name: str, max_depth: int) -> Dict:
        try:
            sql = text(
                """
                WITH RECURSIVE col_up AS (
                    -- seed: any row where target_column matches
                    SELECT
                        cl.source_table,
                        cl.source_column,
                        cl.target_table,
                        cl.target_column,
                        cl.transformation,
                        cl.transformation_type,
                        cl.dag_id,
                        1                                                       AS depth,
                        ARRAY[cl.source_table || '.' || cl.source_column]       AS visited_path
                    FROM column_lineage cl
                    WHERE cl.target_column = :column_name

                    UNION ALL

                    SELECT
                        cl.source_table,
                        cl.source_column,
                        cl.target_table,
                        cl.target_column,
                        cl.transformation,
                        cl.transformation_type,
                        cl.dag_id,
                        cu.depth + 1,
                        cu.visited_path || (cl.source_table || '.' || cl.source_column)
                    FROM column_lineage cl
                    JOIN col_up cu
                      ON cl.target_table  = cu.source_table
                     AND cl.target_column = cu.source_column
                    WHERE cu.depth < :max_depth
                      AND NOT (
                            (cl.source_table || '.' || cl.source_column) = ANY(cu.visited_path)
                          )
                )
                SELECT source_table, source_column, target_table, target_column,
                       transformation, transformation_type, dag_id, depth
                FROM col_up
                ORDER BY depth, source_table, source_column;
                """
            )
            rows = db.execute(
                sql, {"column_name": column_name, "max_depth": max_depth}
            ).fetchall()
            chain = [self._row_to_dict(r) for r in rows]
            return self._upstream_result(column_name, max_depth, chain)
        except Exception:
            logger.exception("PG upstream failed | column=%s", column_name)
            raise

    def _upstream_python(self, db: Session, column_name: str, max_depth: int) -> Dict:
        """Python BFS fallback for non-PostgreSQL dialects."""
        visited_edges: set = set()
        chain: List[Dict] = []
        # seed: find all (table, column_name) combos that have this column as target
        seeds = (
            db.query(ColumnLineage)
            .filter(ColumnLineage.target_column == column_name)
            .all()
        )
        queue: deque = deque()
        visited_cols: set = set()
        for s in seeds:
            key = (s.source_table, s.source_column, s.target_table, s.target_column)
            if key not in visited_edges:
                visited_edges.add(key)
                chain.append({**s.to_dict(), "depth": 1})
                src = (s.source_table, s.source_column)
                if src not in visited_cols:
                    visited_cols.add(src)
                    queue.append((src, 1))

        while queue:
            (cur_tbl, cur_col), depth = queue.popleft()
            if depth >= max_depth:
                continue
            edges = (
                db.query(ColumnLineage)
                .filter(
                    ColumnLineage.target_table == cur_tbl,
                    ColumnLineage.target_column == cur_col,
                )
                .all()
            )
            for e in edges:
                key = (e.source_table, e.source_column, e.target_table, e.target_column)
                if key not in visited_edges:
                    visited_edges.add(key)
                    chain.append({**e.to_dict(), "depth": depth + 1})
                    src = (e.source_table, e.source_column)
                    if src not in visited_cols:
                        visited_cols.add(src)
                        queue.append((src, depth + 1))

        chain.sort(key=lambda x: (x["depth"], x["source_table"], x["source_column"]))
        return self._upstream_result(column_name, max_depth, chain)

    @staticmethod
    def _upstream_result(column_name: str, max_depth: int, chain: List[Dict]) -> Dict:
        upstream_cols = sorted({f"{e['source_table']}.{e['source_column']}" for e in chain})
        logger.info(
            "Upstream complete | column=%s edges=%d unique_sources=%d",
            column_name, len(chain), len(upstream_cols),
        )
        return {
            "column": column_name,
            "direction": "upstream",
            "depth_limit": max_depth,
            "total_edges": len(chain),
            "upstream_columns": upstream_cols,
            "lineage_chain": chain,
        }

    # ------------------------------------------------------------------
    # Cross-table downstream (by column name only)
    # ------------------------------------------------------------------

    def fetch_downstream(
        self,
        db: Session,
        column_name: str,
        max_depth: int = _DEFAULT_MAX_DEPTH,
    ) -> Dict:
        """
        Return all column-level targets that depend on any column named
        *column_name* (across all tables).
        """
        logger.info(
            "fetch_downstream | column=%s max_depth=%d dialect=%s",
            column_name, max_depth, _dialect(db),
        )
        if _dialect(db) == "postgresql":
            return self._downstream_pg(db, column_name, max_depth)
        return self._downstream_python(db, column_name, max_depth)

    def _downstream_pg(self, db: Session, column_name: str, max_depth: int) -> Dict:
        try:
            sql = text(
                """
                WITH RECURSIVE col_down AS (
                    -- seed: any row where source_column matches
                    SELECT
                        cl.source_table,
                        cl.source_column,
                        cl.target_table,
                        cl.target_column,
                        cl.transformation,
                        cl.transformation_type,
                        cl.dag_id,
                        1                                                       AS depth,
                        ARRAY[cl.target_table || '.' || cl.target_column]       AS visited_path
                    FROM column_lineage cl
                    WHERE cl.source_column = :column_name

                    UNION ALL

                    SELECT
                        cl.source_table,
                        cl.source_column,
                        cl.target_table,
                        cl.target_column,
                        cl.transformation,
                        cl.transformation_type,
                        cl.dag_id,
                        cd.depth + 1,
                        cd.visited_path || (cl.target_table || '.' || cl.target_column)
                    FROM column_lineage cl
                    JOIN col_down cd
                      ON cl.source_table  = cd.target_table
                     AND cl.source_column = cd.target_column
                    WHERE cd.depth < :max_depth
                      AND NOT (
                            (cl.target_table || '.' || cl.target_column) = ANY(cd.visited_path)
                          )
                )
                SELECT source_table, source_column, target_table, target_column,
                       transformation, transformation_type, dag_id, depth
                FROM col_down
                ORDER BY depth, target_table, target_column;
                """
            )
            rows = db.execute(
                sql, {"column_name": column_name, "max_depth": max_depth}
            ).fetchall()
            chain = [self._row_to_dict(r) for r in rows]
            return self._downstream_result(column_name, max_depth, chain)
        except Exception:
            logger.exception("PG downstream failed | column=%s", column_name)
            raise

    def _downstream_python(self, db: Session, column_name: str, max_depth: int) -> Dict:
        """Python BFS fallback for non-PostgreSQL dialects."""
        visited_edges: set = set()
        chain: List[Dict] = []
        seeds = (
            db.query(ColumnLineage)
            .filter(ColumnLineage.source_column == column_name)
            .all()
        )
        queue: deque = deque()
        visited_cols: set = set()
        for s in seeds:
            key = (s.source_table, s.source_column, s.target_table, s.target_column)
            if key not in visited_edges:
                visited_edges.add(key)
                chain.append({**s.to_dict(), "depth": 1})
                tgt = (s.target_table, s.target_column)
                if tgt not in visited_cols:
                    visited_cols.add(tgt)
                    queue.append((tgt, 1))

        while queue:
            (cur_tbl, cur_col), depth = queue.popleft()
            if depth >= max_depth:
                continue
            edges = (
                db.query(ColumnLineage)
                .filter(
                    ColumnLineage.source_table == cur_tbl,
                    ColumnLineage.source_column == cur_col,
                )
                .all()
            )
            for e in edges:
                key = (e.source_table, e.source_column, e.target_table, e.target_column)
                if key not in visited_edges:
                    visited_edges.add(key)
                    chain.append({**e.to_dict(), "depth": depth + 1})
                    tgt = (e.target_table, e.target_column)
                    if tgt not in visited_cols:
                        visited_cols.add(tgt)
                        queue.append((tgt, depth + 1))

        chain.sort(key=lambda x: (x["depth"], x["target_table"], x["target_column"]))
        return self._downstream_result(column_name, max_depth, chain)

    @staticmethod
    def _downstream_result(column_name: str, max_depth: int, chain: List[Dict]) -> Dict:
        downstream_cols = sorted({f"{e['target_table']}.{e['target_column']}" for e in chain})
        logger.info(
            "Downstream complete | column=%s edges=%d unique_targets=%d",
            column_name, len(chain), len(downstream_cols),
        )
        return {
            "column": column_name,
            "direction": "downstream",
            "depth_limit": max_depth,
            "total_edges": len(chain),
            "downstream_columns": downstream_cols,
            "lineage_chain": chain,
        }

    # ------------------------------------------------------------------
    # Transformation type summary
    # ------------------------------------------------------------------

    def transformation_summary(self, db: Session) -> List[Dict]:
        """
        Return edge counts grouped by transformation_type, ordered descending.

        Example:
          [
            {"transformation_type": "DIRECT",        "count": 42},
            {"transformation_type": "AGGREGATE_SUM",  "count": 17},
            ...
          ]
        """
        logger.debug("Building transformation summary")
        try:
            rows = db.execute(
                text(
                    """
                    SELECT transformation_type, COUNT(*) AS cnt
                    FROM column_lineage
                    GROUP BY transformation_type
                    ORDER BY cnt DESC;
                    """
                )
            ).fetchall()
            return [
                {"transformation_type": r.transformation_type, "count": int(r.cnt)}
                for r in rows
            ]
        except Exception:
            logger.exception("Failed to build transformation summary")
            raise

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(r) -> Dict:
        return {
            "source_table": r.source_table,
            "source_column": r.source_column,
            "target_table": r.target_table,
            "target_column": r.target_column,
            "transformation": r.transformation,
            "transformation_type": r.transformation_type,
            "dag_id": r.dag_id,
            "depth": r.depth,
        }
