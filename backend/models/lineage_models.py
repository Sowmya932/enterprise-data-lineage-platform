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


# ============================================================
# Recursive lineage graph models  (Week 2 Day 1)
# ============================================================

class LineageRelationshipCreate(BaseModel):
    """Request body for creating a single lineage relationship."""

    source_table: str = Field(..., description="Source table name (data origin)")
    target_table: str = Field(..., description="Target table name (data destination)")
    column_name: Optional[str] = Field(None, description="Target column name")
    source_column: Optional[str] = Field(None, description="Source column name")
    dag_id: Optional[str] = Field(None, description="DAG identifier that produces this lineage")

    @model_validator(mode="after")
    def _validate_tables_differ(self) -> "LineageRelationshipCreate":
        if self.source_table == self.target_table:
            raise ValueError("source_table and target_table must be different.")
        return self


class LineageRelationshipResponse(BaseModel):
    """Response payload for a persisted lineage relationship."""

    id: int
    source_table: str
    target_table: str
    column_name: Optional[str] = None
    source_column: Optional[str] = None
    dag_id: Optional[str] = None
    created_at: Optional[str] = None


class RecursiveLineageEdge(BaseModel):
    """One edge in a recursive upstream/downstream lineage chain."""

    source_table: str
    target_table: str
    column_name: Optional[str] = None
    source_column: Optional[str] = None
    dag_id: Optional[str] = None
    depth: int = Field(..., description="Distance (hops) from the root table (1-indexed)")


class UpstreamLineageResponse(BaseModel):
    """Response for GET /upstream/{table_name}."""

    table: str = Field(..., description="The table whose upstream lineage was queried")
    direction: str = Field("upstream", description="Traversal direction")
    depth_limit: int = Field(..., description="Maximum depth used in the query")
    total_edges: int = Field(..., description="Total number of lineage edges found")
    upstream_tables: List[str] = Field(
        default_factory=list,
        description="Deduplicated list of all upstream source tables",
    )
    lineage_chain: List[RecursiveLineageEdge] = Field(
        default_factory=list,
        description="Full recursive upstream lineage chain, ordered by depth",
    )


class DownstreamLineageResponse(BaseModel):
    """Response for GET /downstream/{table_name}."""

    table: str = Field(..., description="The table whose downstream lineage was queried")
    direction: str = Field("downstream", description="Traversal direction")
    depth_limit: int = Field(..., description="Maximum depth used in the query")
    total_edges: int = Field(..., description="Total number of lineage edges found")
    downstream_tables: List[str] = Field(
        default_factory=list,
        description="Deduplicated list of all downstream target tables",
    )
    lineage_chain: List[RecursiveLineageEdge] = Field(
        default_factory=list,
        description="Full recursive downstream lineage chain, ordered by depth",
    )


class DependencyGraphNode(BaseModel):
    """A table node in the full dependency graph."""

    id: int
    name: str
    schema_name: Optional[str] = None


class DependencyGraphEdge(BaseModel):
    """An edge in the full dependency graph."""

    id: int
    source: str
    target: str
    column_name: Optional[str] = None
    source_column: Optional[str] = None
    dag_id: Optional[str] = None
    created_at: Optional[str] = None


class DependencyGraphResponse(BaseModel):
    """Full lineage graph for visualisation (nodes + edges)."""

    nodes: List[DependencyGraphNode] = Field(default_factory=list)
    edges: List[DependencyGraphEdge] = Field(default_factory=list)


# ============================================================
# Column-level lineage models
# ============================================================

class ColumnLineageCreate(BaseModel):
    """Request body for creating a single column-level lineage edge."""

    source_table: str = Field(..., description="Table the data originates from")
    source_column: str = Field(..., description="Column the data originates from")
    target_table: str = Field(..., description="Table the data flows into")
    target_column: str = Field(..., description="Column the data flows into")
    transformation: Optional[str] = Field(
        None,
        description="SQL expression that derives target_column from source_column",
    )
    dag_id: Optional[str] = Field(None, description="DAG that produces this lineage")

    @model_validator(mode="after")
    def _validate_not_self_referential(self) -> "ColumnLineageCreate":
        if self.source_table == self.target_table and self.source_column == self.target_column:
            raise ValueError(
                "source_table.source_column and target_table.target_column must differ."
            )
        return self


class ColumnLineageResponse(BaseModel):
    """Response payload for a persisted column-level lineage edge."""

    id: int
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    transformation: Optional[str] = None
    transformation_type: str = "DIRECT"
    dag_id: Optional[str] = None
    created_at: Optional[str] = None


class ColumnLineageEdge(BaseModel):
    """One hop in a column-level upstream or downstream traversal chain."""

    source_table: str
    source_column: str
    target_table: str
    target_column: str
    transformation: Optional[str] = None
    transformation_type: str = "DIRECT"
    dag_id: Optional[str] = None
    depth: int = Field(..., description="Distance (hops) from the root column (1-indexed)")


class ColumnUpstreamResponse(BaseModel):
    """Response for GET /column-upstream/{table}/{column}."""

    table: str = Field(..., description="Table whose upstream column lineage was queried")
    column: str = Field(..., description="Column whose upstream lineage was queried")
    direction: str = Field("upstream")
    depth_limit: int
    total_edges: int
    upstream_columns: List[str] = Field(
        default_factory=list,
        description="Deduplicated list of upstream columns in 'table.column' format",
    )
    lineage_chain: List[ColumnLineageEdge] = Field(default_factory=list)


class ColumnDownstreamResponse(BaseModel):
    """Response for GET /column-downstream/{table}/{column}."""

    table: str = Field(..., description="Table whose downstream column lineage was queried")
    column: str = Field(..., description="Column whose downstream lineage was queried")
    direction: str = Field("downstream")
    depth_limit: int
    total_edges: int
    downstream_columns: List[str] = Field(
        default_factory=list,
        description="Deduplicated list of downstream columns in 'table.column' format",
    )
    lineage_chain: List[ColumnLineageEdge] = Field(default_factory=list)


# ============================================================
# Column service models  (column_service.py / column_lineage router)
# ============================================================

class ColumnLineageEdgeFull(BaseModel):
    """Full edge row returned by column_service traversals (includes transformation_type)."""

    source_table: str
    source_column: str
    target_table: str
    target_column: str
    transformation: Optional[str] = None
    transformation_type: str = "DIRECT"
    dag_id: Optional[str] = None
    depth: int


class ColumnGlobalUpstreamResponse(BaseModel):
    """Response for GET /column/upstream/{column_name} (cross-table search)."""

    column: str
    direction: str = "upstream"
    depth_limit: int
    total_edges: int
    upstream_columns: List[str] = Field(
        default_factory=list,
        description="Deduplicated upstream columns in 'table.column' format",
    )
    lineage_chain: List[ColumnLineageEdgeFull] = Field(default_factory=list)


class ColumnGlobalDownstreamResponse(BaseModel):
    """Response for GET /column/downstream/{column_name} (cross-table search)."""

    column: str
    direction: str = "downstream"
    depth_limit: int
    total_edges: int
    downstream_columns: List[str] = Field(
        default_factory=list,
        description="Deduplicated downstream columns in 'table.column' format",
    )
    lineage_chain: List[ColumnLineageEdgeFull] = Field(default_factory=list)


class ColumnParseSQLRequest(BaseModel):
    """Request body for POST /column/parse-sql."""

    sql: str = Field(..., description="SQL statement to parse (INSERT INTO … SELECT …)")
    dialect: str = Field("postgres", description="SQL dialect (postgres, mysql, snowflake, etc.)")
    dag_id: Optional[str] = Field(None, description="DAG that runs this SQL (optional)")


class ColumnParseSQLResponse(BaseModel):
    """Response for POST /column/parse-sql."""

    target_table: Optional[str]
    edges_saved: int
    edges_skipped: int
    edges: List[ColumnLineageEdgeFull] = Field(default_factory=list)
    error: Optional[str] = None


class TransformationTypeStat(BaseModel):
    """One row of the transformation-type summary."""

    transformation_type: str
    count: int


class TransformationSummaryResponse(BaseModel):
    """Response for GET /column/transformations."""

    total_edges: int
    by_type: List[TransformationTypeStat] = Field(default_factory=list)


# ============================================================
# Impact Analysis models  (Week 2 Day 3)
# ============================================================

class ImpactedDAGDetail(BaseModel):
    """One DAG entry in an impact analysis result."""

    dag_id: str = Field(..., description="Airflow DAG identifier")
    affected_table: str = Field(..., description="Downstream table touched by this DAG")
    depth: int = Field(..., description="Hop distance from the change origin (0 = direct)")


class ImpactedColumnDetail(BaseModel):
    """One downstream column entry in an impact analysis result."""

    table: str = Field(..., description="Table that owns the affected column")
    column: str = Field(..., description="Column name")
    transformation_type: str = Field(
        ...,
        description=(
            "How the column is derived: DIRECT, ALIAS, AGGREGATE_SUM, "
            "AGGREGATE_COUNT, AGGREGATE_AVG, AGGREGATE_MAX, AGGREGATE_MIN, "
            "CASE_WHEN, or DERIVED"
        ),
    )
    depth: int = Field(..., description="Hop distance from the change origin (1-indexed)")


class TableImpactResponse(BaseModel):
    """
    Response for GET /impact/table/{table_name}.

    Severity scale (based on unique affected downstream tables):
        NONE     – 0
        LOW      – 1-5
        MEDIUM   – 6-15
        HIGH     – 16-30
        CRITICAL – 31+
    """

    source_table: str = Field(..., description="Table whose change is being assessed")
    severity: str = Field(
        ...,
        description="Impact severity: NONE | LOW | MEDIUM | HIGH | CRITICAL",
    )
    affected_tables: List[str] = Field(
        default_factory=list,
        description="Sorted list of all downstream tables that will be affected",
    )
    impacted_dags: List[str] = Field(
        default_factory=list,
        description="Sorted list of distinct DAG IDs that must be re-evaluated",
    )
    total_edges: int = Field(..., description="Total lineage edges traversed")
    depth_limit: int = Field(..., description="Maximum depth cap used in the query")
    lineage_chain: List[RecursiveLineageEdge] = Field(
        default_factory=list,
        description="Full downstream edge chain ordered by depth",
    )
    dag_details: List[ImpactedDAGDetail] = Field(
        default_factory=list,
        description="Per-DAG breakdown of which table at which depth was affected",
    )


class ColumnImpactResponse(BaseModel):
    """
    Response for GET /impact/column/{column_name}.

    When called without a specific source table the source_table field is null
    (global column-name search across all tables).
    """

    source_table: Optional[str] = Field(
        None,
        description="Source table, or null when searching globally by column name",
    )
    source_column: str = Field(..., description="Column name that is changing")
    severity: str = Field(
        ...,
        description="Impact severity: NONE | LOW | MEDIUM | HIGH | CRITICAL",
    )
    affected_tables: List[str] = Field(
        default_factory=list,
        description="Sorted list of all downstream tables that own affected columns",
    )
    affected_columns: List[ImpactedColumnDetail] = Field(
        default_factory=list,
        description="All downstream columns derived from the changed column",
    )
    impacted_dags: List[str] = Field(
        default_factory=list,
        description="Sorted list of distinct DAG IDs that must be re-evaluated",
    )
    total_hops: int = Field(..., description="Total column-lineage edges traversed")
    depth_limit: int = Field(..., description="Maximum depth cap used in the query")
    dag_details: List[ImpactedDAGDetail] = Field(
        default_factory=list,
        description="Per-DAG breakdown of which table at which depth was affected",
    )

