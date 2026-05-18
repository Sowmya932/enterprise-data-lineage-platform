from fastapi import APIRouter
from backend.models.lineage_models import LineageRequest, LineageResponse, LineageResult
from backend.parsers.sql_parser import SQLParser

router = APIRouter()


@router.post("/parse-sql", response_model=LineageResponse)
def parse_sql(request: LineageRequest):
    """
    Parse a SQL query and return lineage metadata.

    - **sql**: SQL query string to parse
    - **dialect**: SQL dialect (postgres, mysql, snowflake, bigquery, etc.)
    """
    parser = SQLParser(dialect=request.dialect)
    result = parser.parse(request.sql)

    if "error" in result:
        return LineageResponse(
            success=False,
            error=result["error"],
            raw_sql=request.sql
        )

    col_lineage_result = parser.extract_column_lineage(request.sql)
    column_lineage = col_lineage_result.get("column_lineage") if "error" not in col_lineage_result else None

    return LineageResponse(
        success=True,
        lineage=LineageResult(
            target_table=result["target_table"],
            source_tables=result["source_tables"],
            column_lineage=column_lineage,
        ),
        raw_sql=request.sql
    )
