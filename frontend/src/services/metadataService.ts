import { apiClient } from './apiClient';
import type { MetadataResponse } from '../types/api';

export async function getMetadata(): Promise<MetadataResponse> {
  const { data } = await apiClient.get<MetadataResponse>('/metadata');
  return data;
}
