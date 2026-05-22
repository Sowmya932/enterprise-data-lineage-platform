"""
column_lineage.py
-----------------
FastAPI router for column-level lineage endpoints.

Routes
------
    POST /column/parse-sql
        Parse a SQL statement and persist all column-level lineage edges,
        classifying each as DIRECT / ALIAS / AGGREGATE_* / CASE_WHEN / DERIVED.

    GET  /column/upstream/{column_name}
        Recursively fetch all column-level sources that feed into any column
        named *column_name* across all tables (cross-table global search).

    GET  /column/downstream/{column_name}
        Recursively fetch all column-level targets that depend on any column
        named *column_name* across all tables.

    GET  /column/transformations
        Return a summary of edge counts grouped by transformation_type.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.lineage.column_service import ColumnLineageService
from backend.models.lineage_models import (
    ColumnGlobalDownstreamResponse,
    ColumnGlobalUpstreamResponse,
    ColumnParseSQLRequest,
    ColumnParseSQLResponse,
    TransformationSummaryResponse,
    TransformationTypeStat,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/column", tags=["Column Lineage"])

_col_svc = ColumnLineageService()


# ============================================================
# POST /column/parse-sql
# ============================================================

@router.post(
    "/parse-sql",
    response_model=ColumnParseSQLResponse,
    status_code=201,
    summary="Parse SQL and save column lineage",
    description=(
        "Parse an INSERT INTO … SELECT … (or CREATE TABLE AS SELECT) statement "
        "and persist every column-level lineage edge found. Each edge is "
        "classified as DIRECT, ALIAS, AGGREGATE_SUM/COUNT/AVG/MAX/MIN, "
        "CASE_WHEN, or DERIVED. Duplicate edges are silently skipped."
    ),
)
def parse_sql_column_lineage(
    request: ColumnParseSQLRequest,
    db: Session = Depends(get_db),
) -> ColumnParseSQLResponse:
    """Extract and persist column-level lineage from a SQL statement."""
    try:
        result = _col_svc.save_from_sql(
            db,
            request.sql,
            dialect=request.dialect,
            dag_id=request.dag_id,
        )
        return ColumnParseSQLResponse(**result)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to parse SQL for column lineage")
        raise HTTPException(status_code=500, detail="Internal server error.")


# ============================================================
# GET /column/upstream/{column_name}
# ============================================================

@router.get(
    "/upstream/{column_name}",
    response_model=ColumnGlobalUpstreamResponse,
    summary="Global column upstream traversal",
    description=(
        "Recursively find all column-level sources that feed into any column "
        "named *column_name* across all tables. Uses a PostgreSQL WITH RECURSIVE "
        "CTE seeded on target_column. Returns transformation types at every hop."
    ),
)
def get_column_upstream(
    column_name: str,
    max_depth: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum upstream hops to traverse (1–50).",
    ),
    db: Session = Depends(get_db),
) -> ColumnGlobalUpstreamResponse:
    """Traverse column_lineage upstream from any column named *column_name*."""
    try:
        result = _col_svc.fetch_upstream(db, column_name, max_depth=max_depth)
        return ColumnGlobalUpstreamResponse(**result)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error in column upstream | column=%s", column_name)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch upstream lineage for column '{column_name}'.",
        )


# ============================================================
# GET /column/downstream/{column_name}
# ============================================================

@router.get(
    "/downstream/{column_name}",
    response_model=ColumnGlobalDownstreamResponse,
    summary="Global column downstream traversal",
    description=(
        "Recursively find all column-level targets that depend on any column "
        "named *column_name* across all tables. Uses a PostgreSQL WITH RECURSIVE "
        "CTE seeded on source_column. Returns transformation types at every hop."
    ),
)
def get_column_downstream(
    column_name: str,
    max_depth: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum downstream hops to traverse (1–50).",
    ),
    db: Session = Depends(get_db),
) -> ColumnGlobalDownstreamResponse:
    """Traverse column_lineage downstream from any column named *column_name*."""
    try:
        result = _col_svc.fetch_downstream(db, column_name, max_depth=max_depth)
        return ColumnGlobalDownstreamResponse(**result)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error in column downstream | column=%s", column_name)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch downstream lineage for column '{column_name}'.",
        )


# ============================================================
# GET /column/transformations
# ============================================================

@router.get(
    "/transformations",
    response_model=TransformationSummaryResponse,
    summary="Transformation type summary",
    description=(
        "Return the count of column lineage edges grouped by transformation_type "
        "(DIRECT, ALIAS, AGGREGATE_SUM, AGGREGATE_COUNT, AGGREGATE_AVG, "
        "AGGREGATE_MAX, AGGREGATE_MIN, CASE_WHEN, DERIVED)."
    ),
)
def get_transformation_summary(
    db: Session = Depends(get_db),
) -> TransformationSummaryResponse:
    """Count column_lineage edges by transformation_type."""
    try:
        stats = _col_svc.transformation_summary(db)
        total = sum(s["count"] for s in stats)
        return TransformationSummaryResponse(
            total_edges=total,
            by_type=[TransformationTypeStat(**s) for s in stats],
        )
    except Exception:
        logger.exception("Error fetching transformation summary")
        raise HTTPException(status_code=500, detail="Failed to fetch transformation summary.")
