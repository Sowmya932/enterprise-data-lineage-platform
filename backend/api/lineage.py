import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.models.lineage_models import LineageRequest, LineageResponse, LineageResult
from backend.parsers.sql_parser import SQLParser
from backend.services.lineage_service import save_lineage_metadata

logger = logging.getLogger(__name__)

router = APIRouter(tags=["SQL Lineage"])


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
