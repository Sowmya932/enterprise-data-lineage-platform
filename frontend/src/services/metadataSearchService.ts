import { apiClient } from './apiClient';
import { searchColumns, searchDags, searchTables } from './searchService';
import type {
  ColumnMetadataDetails,
  ColumnRecord,
  DagMetadataDetails,
  DagRecord,
  MetadataAsset,
  MetadataAssetType,
  MetadataSearchBundle,
  MetadataSuggestion,
  TableMetadataDetails,
  TableRecord,
} from '../types/api';

interface MetadataSearchOptions {
  query: string;
  include: MetadataAssetType[];
  limitPerType?: number;
}

function toTableAsset(record: TableRecord): MetadataAsset {
  return {
    id: `table-${record.name}`,
    type: 'table',
    title: record.name,
    subtitle: record.schema_name ? `Schema: ${record.schema_name}` : undefined,
    tableName: record.name,
    record,
  };
}

function toColumnAsset(record: ColumnRecord): MetadataAsset {
  const tableName = record.table_name ?? '';
  return {
    id: `column-${tableName}-${record.name}-${record.id}`,
    type: 'column',
    title: record.name,
    subtitle: tableName ? `Table: ${tableName}` : undefined,
    tableName,
    columnName: record.name,
    record,
  };
}

function toDagAsset(record: DagRecord): MetadataAsset {
  return {
    id: `dag-${record.dag_id}`,
    type: 'dag',
    title: record.dag_id,
    subtitle: `${record.task_count ?? record.tasks?.length ?? 0} task(s)`,
    dagId: record.dag_id,
    record,
  };
}

function buildSuggestion(asset: MetadataAsset): MetadataSuggestion {
  return {
    id: asset.id,
    label: asset.title,
    description: asset.subtitle,
    type: asset.type,
    asset,
  };
}

export async function searchMetadataAssets(options: MetadataSearchOptions): Promise<MetadataSearchBundle> {
  const query = options.query.trim();
  if (!query) {
    return {
      query,
      results: [],
      byType: { tables: [], columns: [], dags: [] },
      suggestions: [],
      total: 0,
    };
  }

  const include = new Set(options.include);
  const limit = options.limitPerType ?? 30;

  const [tableResult, columnResult, dagResult] = await Promise.all([
    include.has('table')
      ? searchTables({ query, limit, offset: 0 })
      : Promise.resolve({ items: [] as TableRecord[], pagination: { total: 0, limit, offset: 0, has_next: false } }),
    include.has('column')
      ? searchColumns({ query, limit, offset: 0 })
      : Promise.resolve({ items: [] as ColumnRecord[], pagination: { total: 0, limit, offset: 0, has_next: false } }),
    include.has('dag')
      ? searchDags({ query, limit, offset: 0 })
      : Promise.resolve({ items: [] as DagRecord[], pagination: { total: 0, limit, offset: 0, has_next: false } }),
  ]);

  const tables = tableResult.items.map(toTableAsset);
  const columns = columnResult.items.map(toColumnAsset);
  const dags = dagResult.items.map(toDagAsset);

  const results = [...tables, ...columns, ...dags].sort((a, b) => a.title.localeCompare(b.title));

  return {
    query,
    results,
    byType: {
      tables,
      columns,
      dags,
    },
    suggestions: results.slice(0, 8).map(buildSuggestion),
    total:
      (tableResult.pagination?.total ?? 0) +
      (columnResult.pagination?.total ?? 0) +
      (dagResult.pagination?.total ?? 0),
  };
}

export async function getTableMetadataDetails(
  tableName: string,
  maxDepth = 10,
): Promise<TableMetadataDetails> {
  const { data } = await apiClient.get<TableMetadataDetails>(`/table/${encodeURIComponent(tableName)}`, {
    params: { max_depth: maxDepth },
  });
  return data;
}

export async function getColumnMetadataDetails(
  columnName: string,
  options?: { tableName?: string; maxDepth?: number },
): Promise<ColumnMetadataDetails> {
  const { data } = await apiClient.get<ColumnMetadataDetails>(`/column/${encodeURIComponent(columnName)}`, {
    params: {
      table_name: options?.tableName,
      max_depth: options?.maxDepth ?? 10,
    },
  });
  return data;
}

export async function getDagMetadataDetails(dagName: string): Promise<DagMetadataDetails> {
  const { data } = await apiClient.get<DagMetadataDetails>(`/dag/${encodeURIComponent(dagName)}`);
  return data;
}
