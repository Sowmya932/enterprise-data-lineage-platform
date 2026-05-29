import { apiClient } from './apiClient';
import type {
  ColumnRecord,
  DagRecord,
  LineageRelationship,
  SearchResponse,
  TableRecord,
} from '../types/api';

export interface SearchQueryOptions {
  query: string;
  matchType?: 'partial' | 'exact';
  limit?: number;
  offset?: number;
}

function buildBaseParams(options: SearchQueryOptions): URLSearchParams {
  const params = new URLSearchParams();
  params.set('q', options.query);
  params.set('match_type', options.matchType ?? 'partial');
  params.set('limit', String(options.limit ?? 20));
  params.set('offset', String(options.offset ?? 0));
  return params;
}

export async function searchTables(options: SearchQueryOptions): Promise<SearchResponse<TableRecord>> {
  const params = buildBaseParams(options);
  const { data } = await apiClient.get<SearchResponse<TableRecord>>('/search/tables', { params });
  return data;
}

export async function searchColumns(options: SearchQueryOptions): Promise<SearchResponse<ColumnRecord>> {
  const params = buildBaseParams(options);
  const { data } = await apiClient.get<SearchResponse<ColumnRecord>>('/search/columns', { params });
  return data;
}

export async function searchDags(options: SearchQueryOptions): Promise<SearchResponse<DagRecord>> {
  const params = buildBaseParams(options);
  const { data } = await apiClient.get<SearchResponse<DagRecord>>('/search/dags', { params });
  return data;
}

export async function searchLineageRelationships(
  options: SearchQueryOptions,
): Promise<SearchResponse<LineageRelationship>> {
  const params = buildBaseParams(options);
  const { data } = await apiClient.get<SearchResponse<LineageRelationship>>('/search/lineage', { params });
  return data;
}
