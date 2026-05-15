from typing import List, Optional
from pydantic import BaseModel, Field


class LineageResult(BaseModel):
    """Lineage extracted from a single SQL query."""
    target_table: Optional[str] = Field(None, description="Table being written to (INSERT/UPDATE/CREATE)")
    source_tables: List[str] = Field(default_factory=list, description="Tables read by the query")


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
