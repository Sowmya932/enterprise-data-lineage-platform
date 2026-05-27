from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MatchType(str, Enum):
    partial = "partial"
    exact = "exact"


class PaginationMeta(BaseModel):
    total: int = Field(..., description="Total number of rows matching the filter")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Offset from the beginning")
    has_next: bool = Field(..., description="True when more rows are available")


class TableSearchItem(BaseModel):
    id: int
    name: str
    schema_name: Optional[str] = None
    created_at: Optional[str] = None


class ColumnSearchItem(BaseModel):
    id: int
    table_id: int
    table_name: Optional[str] = None
    schema_name: Optional[str] = None
    name: str
    source_expression: Optional[str] = None
    created_at: Optional[str] = None


class DAGSearchItem(BaseModel):
    id: int
    dag_id: str
    task_count: int = 0
    created_at: Optional[str] = None


class LineageRelationshipSearchItem(BaseModel):
    id: int
    source_table: str
    target_table: str
    column_name: Optional[str] = None
    source_column: Optional[str] = None
    dag_id: Optional[str] = None
    created_at: Optional[str] = None


class TableSearchResponse(BaseModel):
    query: str
    match_type: MatchType
    filters: Dict[str, Optional[str]]
    pagination: PaginationMeta
    items: List[TableSearchItem] = Field(default_factory=list)


class ColumnSearchResponse(BaseModel):
    query: str
    match_type: MatchType
    filters: Dict[str, Optional[str]]
    pagination: PaginationMeta
    items: List[ColumnSearchItem] = Field(default_factory=list)


class DAGSearchResponse(BaseModel):
    query: str
    match_type: MatchType
    filters: Dict[str, Optional[str]]
    pagination: PaginationMeta
    items: List[DAGSearchItem] = Field(default_factory=list)


class LineageRelationshipSearchResponse(BaseModel):
    query: str
    match_type: MatchType
    filters: Dict[str, Optional[str]]
    pagination: PaginationMeta
    items: List[LineageRelationshipSearchItem] = Field(default_factory=list)
