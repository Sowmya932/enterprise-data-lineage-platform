import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.models.search_models import (
    ColumnSearchResponse,
    DAGSearchResponse,
    LineageRelationshipSearchResponse,
    MatchType,
    TableSearchResponse,
)
from backend.services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Metadata Search"])
_search = SearchService()


def _validated_identifier(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise HTTPException(status_code=422, detail=f"{field_name} must not be empty.")
    if len(text) > 255:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must be <= 255 characters.",
        )
    return text


@router.get(
    "/search/tables",
    response_model=TableSearchResponse,
    summary="Search table metadata",
    description=(
        "Search catalogued tables using partial or exact matching with optional "
        "schema filtering and pagination."
    ),
)
def search_tables(
    q: str = Query(..., min_length=1, max_length=255, description="Search term"),
    match_type: MatchType = Query(default=MatchType.partial, description="partial or exact"),
    schema_name: Optional[str] = Query(default=None, description="Schema filter (exact)"),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> TableSearchResponse:
    try:
        result = _search.search_tables(
            db,
            q=q.strip(),
            match_type=match_type,
            schema_name=schema_name.strip() if schema_name else None,
            limit=limit,
            offset=offset,
        )
        return TableSearchResponse(**result)
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /search/tables failed")
        raise HTTPException(status_code=500, detail="Failed to search table metadata.")


@router.get(
    "/search/columns",
    response_model=ColumnSearchResponse,
    summary="Search column metadata",
    description=(
        "Search columns using partial or exact matching with optional table/schema "
        "filters and pagination."
    ),
)
def search_columns(
    q: str = Query(..., min_length=1, max_length=255, description="Search term"),
    match_type: MatchType = Query(default=MatchType.partial, description="partial or exact"),
    table_name: Optional[str] = Query(default=None, description="Table filter (exact)"),
    schema_name: Optional[str] = Query(default=None, description="Schema filter (exact)"),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ColumnSearchResponse:
    try:
        result = _search.search_columns(
            db,
            q=q.strip(),
            match_type=match_type,
            table_name=table_name.strip() if table_name else None,
            schema_name=schema_name.strip() if schema_name else None,
            limit=limit,
            offset=offset,
        )
        return ColumnSearchResponse(**result)
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /search/columns failed")
        raise HTTPException(status_code=500, detail="Failed to search column metadata.")


@router.get(
    "/search/dags",
    response_model=DAGSearchResponse,
    summary="Search DAG metadata",
    description=(
        "Search Airflow DAG metadata using partial or exact matching with optional "
        "task-name filtering and pagination."
    ),
)
def search_dags(
    q: str = Query(..., min_length=1, max_length=255, description="Search term"),
    match_type: MatchType = Query(default=MatchType.partial, description="partial or exact"),
    task_name: Optional[str] = Query(default=None, description="Task name filter (partial)"),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> DAGSearchResponse:
    try:
        result = _search.search_dags(
            db,
            q=q.strip(),
            match_type=match_type,
            task_name=task_name.strip() if task_name else None,
            limit=limit,
            offset=offset,
        )
        return DAGSearchResponse(**result)
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /search/dags failed")
        raise HTTPException(status_code=500, detail="Failed to search DAG metadata.")


@router.get(
    "/search/lineage",
    response_model=LineageRelationshipSearchResponse,
    summary="Search lineage relationships",
    description=(
        "Search lineage relationships across source table, target table, columns, "
        "and DAG IDs with optional filtering and pagination."
    ),
)
def search_lineage_relationships(
    q: str = Query(..., min_length=1, max_length=255, description="Search term"),
    match_type: MatchType = Query(default=MatchType.partial, description="partial or exact"),
    source_table: Optional[str] = Query(default=None, description="Source table filter (exact)"),
    target_table: Optional[str] = Query(default=None, description="Target table filter (exact)"),
    dag_id: Optional[str] = Query(default=None, description="DAG ID filter (exact)"),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> LineageRelationshipSearchResponse:
    try:
        result = _search.search_lineage_relationships(
            db,
            q=q.strip(),
            match_type=match_type,
            source_table=source_table.strip() if source_table else None,
            target_table=target_table.strip() if target_table else None,
            dag_id=dag_id.strip() if dag_id else None,
            limit=limit,
            offset=offset,
        )
        return LineageRelationshipSearchResponse(**result)
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /search/lineage failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to search lineage relationship metadata.",
        )


@router.get(
    "/table/{table_name}",
    response_model=Dict[str, Any],
    summary="Get table metadata details",
    description=(
        "Get full metadata for a table including lineage relationships, recursive "
        "dependencies, related DAGs, and impact metadata."
    ),
)
def get_table_metadata(
    table_name: str,
    max_depth: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    table_name = _validated_identifier(table_name, "table_name")
    try:
        return _search.get_table_details(db, table_name, max_depth=max_depth)
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /table/%s failed", table_name)
        raise HTTPException(status_code=500, detail="Failed to fetch table metadata.")


@router.get(
    "/column/{column_name}",
    response_model=Dict[str, Any],
    summary="Get column metadata details",
    description=(
        "Get full metadata for a column including lineage relationships, recursive "
        "dependencies, related DAGs, and impact metadata."
    ),
)
def get_column_metadata(
    column_name: str,
    table_name: Optional[str] = Query(
        default=None,
        description="Optional table scope for this column name.",
    ),
    max_depth: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    column_name = _validated_identifier(column_name, "column_name")
    table_filter = table_name.strip() if table_name else None
    if table_filter is not None:
        table_filter = _validated_identifier(table_filter, "table_name")

    try:
        return _search.get_column_details(
            db,
            column_name,
            table_name=table_filter,
            max_depth=max_depth,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /column/%s failed", column_name)
        raise HTTPException(status_code=500, detail="Failed to fetch column metadata.")


@router.get(
    "/dag/{dag_name}",
    response_model=Dict[str, Any],
    summary="Get DAG metadata details",
    description=(
        "Get full metadata for a DAG including task dependencies, linked lineage "
        "relationships, related entities, and impact metadata."
    ),
)
def get_dag_metadata(dag_name: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    dag_name = _validated_identifier(dag_name, "dag_name")
    try:
        return _search.get_dag_details(db, dag_name)
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /dag/%s failed", dag_name)
        raise HTTPException(status_code=500, detail="Failed to fetch DAG metadata.")
