import { apiClient } from './apiClient';
import type {
  DownstreamLineageResponse,
  UpstreamLineageResponse,
} from '../types/api';

export async function getUpstreamLineage(
  tableName: string,
  maxDepth = 10,
): Promise<UpstreamLineageResponse> {
  const { data } = await apiClient.get<UpstreamLineageResponse>(`/upstream/${encodeURIComponent(tableName)}`, {
    params: { max_depth: maxDepth },
  });
  return data;
}

export async function getDownstreamLineage(
  tableName: string,
  maxDepth = 10,
): Promise<DownstreamLineageResponse> {
  const { data } = await apiClient.get<DownstreamLineageResponse>(
    `/downstream/${encodeURIComponent(tableName)}`,
    {
      params: { max_depth: maxDepth },
    },
  );
  return data;
}
