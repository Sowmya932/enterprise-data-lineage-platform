import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.lineage.graph_service import LineageGraphService
from backend.models.lineage_models import (
    DependencyGraphResponse,
    DownstreamLineageResponse,
    LineageRelationshipCreate,
    LineageRelationshipResponse,
    LineageRequest,
    LineageResponse,
    LineageResult,
    UpstreamLineageResponse,
    ColumnLineageCreate,
    ColumnLineageResponse,
    ColumnUpstreamResponse,
    ColumnDownstreamResponse,
)
from backend.parsers.sql_parser import SQLParser
from backend.services.lineage_service import (
    save_column_lineage,
    save_lineage_metadata,
    save_lineage_relationship,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["SQL Lineage"])

_graph_service = LineageGraphService()


# ============================================================
# POST /parse-sql  – parse & persist SQL lineage
# ============================================================

@router.post("/parse-sql", response_model=LineageResponse)
def parse_sql(request: LineageRequest, db: Session = Depends(get_db)):
    """
    Parse a SQL query and return lineage metadata.

    - **sql**: SQL query string to parse
    - **dialect**: SQL dialect (postgres, mysql, snowflake, bigquery, etc.)

    Parsed lineage is automatically persisted to PostgreSQL.
    """
    parser = SQLParser(dialect=request.dialect)
    result = parser.parse(request.sql)

    if "error" in result:
        return LineageResponse(
            success=False,
            error=result["error"],
            raw_sql=request.sql,
        )

    col_lineage_result = parser.extract_column_lineage(request.sql)
    column_lineage = (
        col_lineage_result.get("column_lineage")
        if "error" not in col_lineage_result
        else None
    )

    # Persist to PostgreSQL
    try:
        save_lineage_metadata(
            db,
            target_table=result.get("target_table"),
            source_tables=result.get("source_tables") or [],
            column_lineage=column_lineage,
        )
    except Exception:
        logger.warning("Could not persist lineage metadata to database", exc_info=True)

    return LineageResponse(
        success=True,
        lineage=LineageResult(
            target_table=result["target_table"],
            source_tables=result["source_tables"],
            column_lineage=column_lineage,
        ),
        raw_sql=request.sql,
    )


# ============================================================
# POST /lineage-relationship  – store a single lineage edge
# ============================================================

@router.post(
    "/lineage-relationship",
    response_model=LineageRelationshipResponse,
    status_code=201,
    summary="Create a lineage relationship",
    description=(
        "Persist a single directed lineage edge (source_table → target_table). "
        "The endpoint validates that the edge will not introduce a circular "
        "dependency before writing to PostgreSQL."
    ),
)
def create_lineage_relationship(
    request: LineageRelationshipCreate,
    db: Session = Depends(get_db),
) -> LineageRelationshipResponse:
    """
    Store a lineage relationship including source/target tables,
    optional column mappings, and an optional DAG identifier.

    Returns the saved relationship with its generated ``id`` and ``created_at``.
    """
    try:
        record = save_lineage_relationship(
            db,
            source_table=request.source_table,
            target_table=request.target_table,
            column_name=request.column_name,
            source_column=request.source_column,
            dag_id=request.dag_id,
        )
        return LineageRelationshipResponse(**record)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to create lineage relationship")
        raise HTTPException(status_code=500, detail="Internal server error.")


# ============================================================
# GET /upstream/{table_name}  – recursive upstream traversal
# ============================================================

@router.get(
    "/upstream/{table_name}",
    response_model=UpstreamLineageResponse,
    summary="Get upstream lineage",
    description=(
        "Return the complete upstream lineage chain for *table_name* using a "
        "PostgreSQL WITH RECURSIVE CTE. Traverses the lineage_relationships graph "
        "in the target → source direction. Supports multi-level dependency chains."
    ),
)
def get_upstream_lineage(
    table_name: str,
    max_depth: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of upstream hops to traverse (1–50).",
    ),
    db: Session = Depends(get_db),
) -> UpstreamLineageResponse:
    """
    Recursively fetch all tables that feed into ``table_name``.

    The response includes:
    - ``upstream_tables``: deduplicated list of all upstream source tables
    - ``lineage_chain``: every edge in the chain with its depth from the root
    """
    try:
        result = _graph_service.fetch_upstream_lineage(
            db, table_name, max_depth=max_depth
        )
        return UpstreamLineageResponse(**result)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching upstream lineage for table=%s", table_name)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch upstream lineage for '{table_name}'.",
        )


# ============================================================
# GET /downstream/{table_name}  – recursive downstream traversal
# ============================================================

@router.get(
    "/downstream/{table_name}",
    response_model=DownstreamLineageResponse,
    summary="Get downstream lineage",
    description=(
        "Return the complete downstream lineage chain for *table_name* using a "
        "PostgreSQL WITH RECURSIVE CTE. Traverses the lineage_relationships graph "
        "in the source → target direction. Supports multi-level dependency chains."
    ),
)
def get_downstream_lineage(
    table_name: str,
    max_depth: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of downstream hops to traverse (1–50).",
    ),
    db: Session = Depends(get_db),
) -> DownstreamLineageResponse:
    """
    Recursively fetch all tables that depend on ``table_name``.

    The response includes:
    - ``downstream_tables``: deduplicated list of all downstream target tables
    - ``lineage_chain``: every edge in the chain with its depth from the root
    """
    try:
        result = _graph_service.fetch_downstream_lineage(
            db, table_name, max_depth=max_depth
        )
        return DownstreamLineageResponse(**result)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching downstream lineage for table=%s", table_name)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch downstream lineage for '{table_name}'.",
        )


# ============================================================
# GET /lineage-graph  – full dependency graph
# ============================================================

@router.get(
    "/lineage-graph",
    response_model=DependencyGraphResponse,
    summary="Full dependency graph",
    description=(
        "Return the entire lineage graph as nodes (tables) and edges "
        "(lineage relationships). Suitable for graph visualisation tools."
    ),
)
def get_lineage_graph(db: Session = Depends(get_db)) -> DependencyGraphResponse:
    """Return every table node and lineage edge stored in PostgreSQL."""
    try:
        result = _graph_service.fetch_full_dependency_graph(db)
        return DependencyGraphResponse(**result)
    except Exception:
        logger.exception("Error fetching full lineage graph")
        raise HTTPException(status_code=500, detail="Failed to fetch lineage graph.")


# ============================================================
# POST /column-lineage  – store a column-level lineage edge
# ============================================================

@router.post(
    "/column-lineage",
    response_model=ColumnLineageResponse,
    status_code=201,
    summary="Create a column-level lineage edge",
    description=(
        "Persist a single directed column-level lineage edge "
        "(source_table.source_column → target_table.target_column). "
        "An optional SQL transformation expression can be stored with the edge."
    ),
)
def create_column_lineage(
    request: ColumnLineageCreate,
    db: Session = Depends(get_db),
) -> ColumnLineageResponse:
    """Store a column-level lineage edge in PostgreSQL."""
    try:
        record = save_column_lineage(
            db,
            source_table=request.source_table,
            source_column=request.source_column,
            target_table=request.target_table,
            target_column=request.target_column,
            transformation=request.transformation,
            dag_id=request.dag_id,
        )
        return ColumnLineageResponse(**record)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to create column lineage edge")
        raise HTTPException(status_code=500, detail="Internal server error.")


# ============================================================
# GET /column-upstream/{table_name}/{column_name}
# ============================================================

@router.get(
    "/column-upstream/{table_name}/{column_name}",
    response_model=ColumnUpstreamResponse,
    summary="Get column-level upstream lineage",
    description=(
        "Recursively traverse all column-level sources that feed into "
        "table_name.column_name using a PostgreSQL WITH RECURSIVE CTE. "
        "Returns each hop's source/target columns and optional transformation."
    ),
)
def get_column_upstream(
    table_name: str,
    column_name: str,
    max_depth: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of upstream column hops to traverse (1–50).",
    ),
    db: Session = Depends(get_db),
) -> ColumnUpstreamResponse:
    """Recursively fetch all column-level sources for table_name.column_name."""
    try:
        result = _graph_service.fetch_column_upstream(
            db, table_name, column_name, max_depth=max_depth
        )
        return ColumnUpstreamResponse(**result)
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Error fetching column upstream | table=%s column=%s",
            table_name, column_name,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch column upstream for '{table_name}.{column_name}'.",
        )


# ============================================================
# GET /column-downstream/{table_name}/{column_name}
# ============================================================

@router.get(
    "/column-downstream/{table_name}/{column_name}",
    response_model=ColumnDownstreamResponse,
    summary="Get column-level downstream lineage",
    description=(
        "Recursively traverse all column-level targets that depend on "
        "table_name.column_name using a PostgreSQL WITH RECURSIVE CTE. "
        "Returns each hop's source/target columns and optional transformation."
    ),
)
def get_column_downstream(
    table_name: str,
    column_name: str,
    max_depth: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of downstream column hops to traverse (1–50).",
    ),
    db: Session = Depends(get_db),
) -> ColumnDownstreamResponse:
    """Recursively fetch all column-level dependents of table_name.column_name."""
    try:
        result = _graph_service.fetch_column_downstream(
            db, table_name, column_name, max_depth=max_depth
        )
        return ColumnDownstreamResponse(**result)
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Error fetching column downstream | table=%s column=%s",
            table_name, column_name,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch column downstream for '{table_name}.{column_name}'.",
        )
