"""
impact.py
---------
FastAPI router for downstream impact analysis.

Routes
------
    GET /impact/table/{table_name}
        Full downstream impact report for a table-level change.
        Returns affected_tables, impacted_dags, lineage_chain, severity.

    GET /impact/column/{column_name}
        Full downstream impact report for a column-level change.
        Optional **table** query parameter scopes the search to a specific
        source table; omit it to search all tables globally.

Severity scale (unique affected downstream tables)
    NONE     – 0
    LOW      – 1-5
    MEDIUM   – 6-15
    HIGH     – 16-30
    CRITICAL – 31+
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.impact_analysis.impact_service import ImpactAnalysisService
from backend.models.lineage_models import (
    ColumnImpactResponse,
    TableImpactResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/impact", tags=["Impact Analysis"])

_impact_svc = ImpactAnalysisService()

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_MAX_DEPTH_LIMIT = 50
_MIN_DEPTH_LIMIT = 1


def _validated_table_name(table_name: str) -> str:
    """Reject clearly invalid table name values early."""
    name = table_name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="table_name must not be empty.")
    if len(name) > 255:
        raise HTTPException(
            status_code=422, detail="table_name must be ≤ 255 characters."
        )
    return name


def _validated_column_name(column_name: str) -> str:
    """Reject clearly invalid column name values early."""
    name = column_name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="column_name must not be empty.")
    if len(name) > 255:
        raise HTTPException(
            status_code=422, detail="column_name must be ≤ 255 characters."
        )
    return name


# ============================================================
# GET /impact/table/{table_name}
# ============================================================

@router.get(
    "/table/{table_name}",
    response_model=TableImpactResponse,
    summary="Downstream impact analysis for a table change",
    description=(
        "Perform a full downstream impact analysis starting from **table_name**.\n\n"
        "Traverses the lineage graph recursively (up to `max_depth` hops) and "
        "returns:\n"
        "- **affected_tables** – every downstream table that will be impacted\n"
        "- **impacted_dags** – every Airflow DAG that must be re-evaluated\n"
        "- **lineage_chain** – the full edge-by-edge traversal path\n"
        "- **dag_details** – per-DAG breakdown (which table, at which depth)\n"
        "- **severity** – `NONE` / `LOW` / `MEDIUM` / `HIGH` / `CRITICAL`\n\n"
        "Circular dependency guards are applied at every hop via a "
        "`visited_path` array (PostgreSQL) or visited-set (other dialects)."
    ),
)
def analyze_table_impact(
    table_name: str,
    max_depth: int = Query(
        default=10,
        ge=_MIN_DEPTH_LIMIT,
        le=_MAX_DEPTH_LIMIT,
        description="Maximum downstream hops to traverse (1–50, default 10).",
    ),
    db: Session = Depends(get_db),
) -> TableImpactResponse:
    """Compute the downstream blast radius for a table-level change."""
    table_name = _validated_table_name(table_name)
    logger.info("POST /impact/table/%s | max_depth=%d", table_name, max_depth)
    try:
        result = _impact_svc.analyze_table_impact(db, table_name, max_depth=max_depth)
        return TableImpactResponse(**result)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error in /impact/table | table=%s", table_name)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze impact for table '{table_name}'.",
        )


# ============================================================
# GET /impact/column/{column_name}
# ============================================================

@router.get(
    "/column/{column_name}",
    response_model=ColumnImpactResponse,
    summary="Downstream impact analysis for a column change",
    description=(
        "Perform a full downstream impact analysis starting from **column_name**.\n\n"
        "Provide the optional **table** query parameter to scope the search to a "
        "specific source table; omit it to search *all* tables that expose a column "
        "with that name (global search).\n\n"
        "Returns:\n"
        "- **affected_columns** – every downstream column derived from the changed "
        "column, with transformation type and depth\n"
        "- **affected_tables** – distinct tables that own those columns\n"
        "- **impacted_dags** – every Airflow DAG that must be re-evaluated\n"
        "- **dag_details** – per-DAG breakdown (which table, at which depth)\n"
        "- **severity** – `NONE` / `LOW` / `MEDIUM` / `HIGH` / `CRITICAL`\n\n"
        "Circular dependency guards are applied at every hop via a "
        "`visited_path` array (PostgreSQL) or visited-set (other dialects)."
    ),
)
def analyze_column_impact(
    column_name: str,
    table: Optional[str] = Query(
        default=None,
        description=(
            "Source table name. "
            "Provide to scope the search to a specific table; "
            "omit to search all tables globally."
        ),
    ),
    max_depth: int = Query(
        default=10,
        ge=_MIN_DEPTH_LIMIT,
        le=_MAX_DEPTH_LIMIT,
        description="Maximum downstream hops to traverse (1–50, default 10).",
    ),
    db: Session = Depends(get_db),
) -> ColumnImpactResponse:
    """Compute the downstream blast radius for a column-level change."""
    column_name = _validated_column_name(column_name)

    if table is not None:
        table = _validated_table_name(table)

    logger.info(
        "GET /impact/column/%s | table=%s max_depth=%d",
        column_name,
        table or "<global>",
        max_depth,
    )
    try:
        if table:
            result = _impact_svc.analyze_column_impact(
                db, table, column_name, max_depth=max_depth
            )
        else:
            result = _impact_svc.analyze_column_impact_by_name(
                db, column_name, max_depth=max_depth
            )
        return ColumnImpactResponse(**result)
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Error in /impact/column | column=%s table=%s", column_name, table
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze impact for column '{column_name}'.",
        )
