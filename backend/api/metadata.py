"""
metadata.py
-----------
FastAPI router for unified metadata endpoints.

Endpoints
---------
GET  /metadata   – combined tables, columns, DAGs, and dependency edges
GET  /tables     – catalogued table records
GET  /dags       – Airflow DAG records with task lists
GET  /lineage    – lineage relationship edges + task dependency edges
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.lineage.metadata_service import MetadataService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Metadata"])

_metadata_service = MetadataService()


# ---------------------------------------------------------------------------
# GET /metadata
# ---------------------------------------------------------------------------

@router.get(
    "/metadata",
    summary="Unified metadata",
    description=(
        "Returns a combined view of all catalogued tables, columns, "
        "Airflow DAGs, and lineage / task-dependency edges stored in PostgreSQL."
    ),
    response_model=Dict[str, Any],
)
def get_metadata(db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        return _metadata_service.get_unified_metadata(db)
    except Exception as exc:
        logger.exception("GET /metadata failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# GET /tables
# ---------------------------------------------------------------------------

@router.get(
    "/tables",
    summary="Catalogued tables",
    description="Returns all table records extracted from SQL lineage parsing.",
    response_model=Dict[str, Any],
)
def get_tables(db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        tables = _metadata_service.get_tables(db)
        return {"tables": tables, "count": len(tables)}
    except Exception as exc:
        logger.exception("GET /tables failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# GET /dags
# ---------------------------------------------------------------------------

@router.get(
    "/dags",
    summary="Airflow DAG records",
    description="Returns all Airflow DAG records with their associated task lists.",
    response_model=Dict[str, Any],
)
def get_dags(db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        dags = _metadata_service.get_dags(db)
        return {"dags": dags, "count": len(dags)}
    except Exception as exc:
        logger.exception("GET /dags failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# GET /lineage
# ---------------------------------------------------------------------------

@router.get(
    "/lineage",
    summary="Lineage and dependency edges",
    description=(
        "Returns all persisted lineage relationships (source→target table edges) "
        "and task dependency edges (upstream→downstream task pairs)."
    ),
    response_model=Dict[str, Any],
)
def get_lineage(db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        return _metadata_service.get_dependencies(db)
    except Exception as exc:
        logger.exception("GET /lineage failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
