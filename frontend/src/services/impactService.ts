import { apiClient } from './apiClient';
import type { ColumnImpactResponse, TableImpactResponse } from '../types/api';

export async function analyzeTableImpact(
  tableName: string,
  maxDepth = 10,
): Promise<TableImpactResponse> {
  const { data } = await apiClient.get<TableImpactResponse>(`/impact/table/${encodeURIComponent(tableName)}`, {
    params: { max_depth: maxDepth },
  });
  return data;
}

export async function analyzeColumnImpact(
  columnName: string,
  options?: { table?: string; maxDepth?: number },
): Promise<ColumnImpactResponse> {
  const { data } = await apiClient.get<ColumnImpactResponse>(`/impact/column/${encodeURIComponent(columnName)}`, {
    params: {
      table: options?.table,
      max_depth: options?.maxDepth ?? 10,
    },
  });
  return data;
}
