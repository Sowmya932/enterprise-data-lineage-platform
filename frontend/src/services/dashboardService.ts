import { getMetadata } from './metadataService';
import type { DashboardSummary } from '../types/api';

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const metadata = await getMetadata();

  return {
    totalTables: metadata.tables.length,
    totalColumns: metadata.columns.length,
    totalDags: metadata.dags.length,
    totalLineageRelationships: metadata.dependencies.lineage_edges.length,
  };
}
