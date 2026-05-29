export interface ApiErrorResponse {
  success?: boolean;
  error_code?: string;
  error_message?: string;
  detail?: string;
  message?: string;
}

export interface TableRecord {
  id: number;
  name: string;
  schema_name?: string | null;
  created_at?: string | null;
}

export interface ColumnRecord {
  id: number;
  table_id: number;
  table_name?: string | null;
  schema_name?: string | null;
  name: string;
  source_expression?: string | null;
  created_at?: string | null;
}

export interface DagRecord {
  id: number;
  dag_id: string;
  tasks?: string[];
  task_count?: number;
  created_at?: string | null;
}

export interface LineageRelationship {
  id: number;
  source_table: string;
  target_table: string;
  column_name?: string | null;
  source_column?: string | null;
  dag_id?: string | null;
  created_at?: string | null;
}

export interface TaskDependency {
  id: number;
  dag_record_id: number;
  upstream_task: string;
  downstream_task: string;
  created_at?: string | null;
}

export interface MetadataResponse {
  tables: TableRecord[];
  columns: ColumnRecord[];
  dags: DagRecord[];
  dependencies: {
    lineage_edges: LineageRelationship[];
    task_edges: TaskDependency[];
  };
}

export interface PaginationMeta {
  total: number;
  limit: number;
  offset: number;
  has_next: boolean;
}

export interface SearchResponse<T> {
  query: string;
  match_type: 'partial' | 'exact';
  filters: Record<string, string | null>;
  pagination: PaginationMeta;
  items: T[];
}

export interface RecursiveLineageEdge {
  source_table: string;
  target_table: string;
  column_name?: string | null;
  source_column?: string | null;
  dag_id?: string | null;
  depth: number;
}

export interface UpstreamLineageResponse {
  table: string;
  direction: 'upstream';
  depth_limit: number;
  total_edges: number;
  upstream_tables: string[];
  lineage_chain: RecursiveLineageEdge[];
}

export interface DownstreamLineageResponse {
  table: string;
  direction: 'downstream';
  depth_limit: number;
  total_edges: number;
  downstream_tables: string[];
  lineage_chain: RecursiveLineageEdge[];
}

export interface ImpactedDagDetail {
  dag_id: string;
  affected_table: string;
  depth: number;
}

export interface ImpactedColumnDetail {
  table: string;
  column: string;
  transformation_type: string;
  depth: number;
}

export interface TableImpactResponse {
  source_table: string;
  severity: string;
  affected_tables: string[];
  impacted_dags: string[];
  total_edges: number;
  depth_limit: number;
  lineage_chain: RecursiveLineageEdge[];
  dag_details: ImpactedDagDetail[];
}

export interface ColumnImpactResponse {
  source_table: string | null;
  source_column: string;
  severity: string;
  affected_tables: string[];
  affected_columns: ImpactedColumnDetail[];
  impacted_dags: string[];
  total_hops: number;
  depth_limit: number;
  dag_details: ImpactedDagDetail[];
}

export interface DashboardSummary {
  totalTables: number;
  totalColumns: number;
  totalDags: number;
  totalLineageRelationships: number;
}
