from typing import Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class LineageResult(BaseModel):
    """Lineage extracted from a single SQL query."""
    target_table: Optional[str] = Field(None, description="Table being written to (INSERT/UPDATE/CREATE)")
    source_tables: List[str] = Field(default_factory=list, description="Tables read by the query")
    column_lineage: Optional[Dict[str, List[str]]] = Field(
        None,
        description="Column-level lineage mapping: {output_column: [source_table.column, ...]}"
    )


class LineageRequest(BaseModel):
    """Request body for lineage extraction."""
    sql: str = Field(..., description="SQL query to parse")
    dialect: str = Field("postgres", description="SQL dialect (postgres, mysql, snowflake, etc.)")


class LineageResponse(BaseModel):
    """API response for a lineage extraction request."""
    success: bool
    lineage: Optional[LineageResult] = None
    error: Optional[str] = None
    raw_sql: str


class TableNode(BaseModel):
    """A single table node in the lineage graph."""
    name: str
    schema_name: Optional[str] = None

    @property
    def full_name(self) -> str:
        return f"{self.schema_name}.{self.name}" if self.schema_name else self.name


class LineageEdge(BaseModel):
    """A directed edge from source table to target table."""
    source: str = Field(..., description="Source table name")
    target: str = Field(..., description="Target table name")
    sql_snippet: Optional[str] = None


class LineageGraph(BaseModel):
    """Full lineage graph composed of nodes and edges."""
    nodes: List[TableNode] = Field(default_factory=list)
    edges: List[LineageEdge] = Field(default_factory=list)


# ============================================================
# DAG lineage models  (Day 4)
# ============================================================

class DAGMetadata(BaseModel):
    """Parsed metadata extracted from an Airflow DAG file."""

    dag: Optional[str] = Field(
        None,
        description="DAG identifier (dag_id) as declared in the DAG() constructor",
    )
    tasks: List[str] = Field(
        default_factory=list,
        description="Ordered list of task_id strings found in the DAG",
    )
    dependencies: List[List[str]] = Field(
        default_factory=list,
        description=(
            "List of [upstream_task_id, downstream_task_id] pairs "
            "derived from >> operator chains"
        ),
    )


class DAGParseRequest(BaseModel):
    """
    Request body for the POST /parse-dag endpoint.

    Provide exactly one of:
        - dag_file_path  – absolute or relative path to a .py DAG file on the server
        - dag_content    – raw Python source code of the DAG
    """

    dag_file_path: Optional[str] = Field(
        None,
        description="Server-side path to a .py Airflow DAG file",
        examples=["airflow_dags/etl_pipeline_dag.py"],
    )
    dag_content: Optional[str] = Field(
        None,
        description="Raw Python source code of an Airflow DAG",
    )

    @model_validator(mode="after")
    def _require_one_input(self) -> "DAGParseRequest":
        if not self.dag_file_path and not self.dag_content:
            raise ValueError("Provide either 'dag_file_path' or 'dag_content'.")
        return self


class DAGParseResponse(BaseModel):
    """API response for the POST /parse-dag endpoint."""

    success: bool = Field(..., description="True when parsing succeeded")
    metadata: Optional[DAGMetadata] = Field(
        None, description="Extracted DAG metadata (present on success)"
    )
    error: Optional[str] = Field(
        None, description="Human-readable error message (present on failure)"
    )


class DAGLineageNode(BaseModel):
    """
    A single task enriched with SQL lineage information.

    Connects the DAG task layer to the SQL transformation layer:
        DAG task → SQL transformations → source tables → target table
    """

    task_id: str = Field(..., description="DAG task identifier")
    sql_transformations: List[str] = Field(
        default_factory=list,
        description="SQL queries associated with this task (embedded in the DAG source)",
    )
    source_tables: List[str] = Field(
        default_factory=list,
        description="Tables read by this task's SQL transformations",
    )
    target_tables: List[str] = Field(
        default_factory=list,
        description="Tables written by this task's SQL transformations",
    )


class DAGFullLineage(BaseModel):
    """
    Full end-to-end lineage graph linking a DAG to its SQL transformations.

    Each task in the DAG is represented as a DAGLineageNode that carries
    the SQL queries it runs and the tables those queries read from / write to.
    """

    dag: Optional[str] = Field(None, description="DAG identifier")
    lineage_nodes: List[DAGLineageNode] = Field(
        default_factory=list,
        description="One node per DAG task, enriched with SQL lineage",
    )
    task_dependencies: List[List[str]] = Field(
        default_factory=list,
        description="Task-level dependency pairs (same format as DAGMetadata.dependencies)",
    )

