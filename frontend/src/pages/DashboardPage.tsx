import { useEffect, useState } from 'react';
import ErrorState from '../components/ErrorState';
import LoadingState from '../components/LoadingState';
import SummaryCard from '../components/SummaryCard';
import { getDashboardSummary } from '../services/dashboardService';
import { getMetadata } from '../services/metadataService';
import type { DashboardSummary, MetadataResponse } from '../types/api';

function DashboardPage(): JSX.Element {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [metadata, setMetadata] = useState<MetadataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = async (): Promise<void> => {
    setLoading(true);
    setError(null);

    try {
      const [summaryData, metadataData] = await Promise.all([
        getDashboardSummary(),
        getMetadata(),
      ]);
      setSummary(summaryData);
      setMetadata(metadataData);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load dashboard';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDashboard();
  }, []);

  if (loading) {
    return <LoadingState label="Loading dashboard insights..." />;
  }

  if (error || !summary || !metadata) {
    return <ErrorState message={error ?? 'Dashboard data is unavailable.'} onRetry={loadDashboard} />;
  }

  return (
    <section className="page-section">
      <div className="section-head">
        <h3>Data Lineage Summary</h3>
        <p>Live inventory of platform metadata and lineage relationships.</p>
      </div>

      <div className="summary-grid">
        <SummaryCard title="Total Tables" value={summary.totalTables} accent="teal" />
        <SummaryCard title="Total Columns" value={summary.totalColumns} accent="amber" />
        <SummaryCard title="Total DAGs" value={summary.totalDags} accent="blue" />
        <SummaryCard
          title="Total Lineage Relationships"
          value={summary.totalLineageRelationships}
          accent="coral"
        />
      </div>

      <div className="panel-grid">
        <article className="panel">
          <h4>Recent Tables</h4>
          <ul>
            {metadata.tables.slice(0, 8).map((table) => (
              <li key={table.id}>{table.schema_name ? `${table.schema_name}.${table.name}` : table.name}</li>
            ))}
          </ul>
        </article>
        <article className="panel">
          <h4>Registered DAGs</h4>
          <ul>
            {metadata.dags.slice(0, 8).map((dag) => (
              <li key={dag.id}>{dag.dag_id}</li>
            ))}
          </ul>
        </article>
      </div>
    </section>
  );
}

export default DashboardPage;
