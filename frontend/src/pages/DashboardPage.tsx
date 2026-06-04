import { useEffect, useState } from 'react';
import { Skeleton } from '@mui/material';
import DependencyPanel from '../components/DependencyPanel';
import ErrorState from '../components/ErrorState';
import MetricCard from '../components/MetricCard';
import SeverityBadge from '../components/SeverityBadge';
import { getDashboardSummary } from '../services/dashboardService';
import { getRecentActivity, type RecentImpactEntry } from '../services/activityService';
import { logger } from '../services/logger';
import { getMetadata } from '../services/metadataService';
import type { DashboardSummary, MetadataResponse } from '../types/api';

interface DashboardActivity {
  searches: string[];
  impacts: RecentImpactEntry[];
  lineageViews: string[];
}

function formatActivityTime(value: string): string {
  const date = new Date(value);
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
}

function DashboardPage(): JSX.Element {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [metadata, setMetadata] = useState<MetadataResponse | null>(null);
  const [activity, setActivity] = useState<DashboardActivity>({
    searches: [],
    impacts: [],
    lineageViews: [],
  });
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

      const recent = getRecentActivity();

      setSummary(summaryData);
      setMetadata(metadataData);
      setActivity({
        searches: recent.recentSearches.map((item) => `${item.label} (${item.type})`),
        impacts: recent.recentImpacts,
        lineageViews: recent.recentLineageViews.map(
          (item) => `${item.label} (${item.direction})`,
        ),
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load dashboard';
      setError(message);
      logger.error('Dashboard load failed', { message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDashboard();
  }, []);

  if (loading) {
    return (
      <section className="page-section">
        <div className="summary-grid">
          {Array.from({ length: 4 }).map((_, index) => (
            <article key={`metric-skeleton-${index}`} className="metric-card">
              <Skeleton height={24} width="72%" />
              <Skeleton height={40} width="48%" />
            </article>
          ))}
        </div>
        <div className="panel-grid">
          <article className="panel">
            <Skeleton height={30} width="56%" />
            <Skeleton height={28} />
            <Skeleton height={28} />
            <Skeleton height={28} />
          </article>
          <article className="panel">
            <Skeleton height={30} width="56%" />
            <Skeleton height={28} />
            <Skeleton height={28} />
            <Skeleton height={28} />
          </article>
        </div>
      </section>
    );
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
        <MetricCard title="Total Tables" value={summary.totalTables} accent="teal" />
        <MetricCard title="Total Columns" value={summary.totalColumns} accent="amber" />
        <MetricCard title="Total DAGs" value={summary.totalDags} accent="blue" />
        <MetricCard
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

      <div className="section-head">
        <h3>Recent Activity</h3>
        <p>Quick context from latest searches, impact analysis, and lineage exploration sessions.</p>
      </div>

      <div className="panel-grid">
        <DependencyPanel
          title="Recently Searched Assets"
          items={activity.searches}
          emptyLabel="No recent searches yet. Use Metadata Search to explore assets."
        />
        <article className="panel dependency-panel">
          <h4>Recently Analyzed Impacts</h4>
          {activity.impacts.length ? (
            <ul>
              {activity.impacts.map((item) => (
                <li key={item.id}>
                  <span>{item.label}</span>
                  <SeverityBadge severity={item.severity} compact />
                  <small>{formatActivityTime(item.timestamp)}</small>
                </li>
              ))}
            </ul>
          ) : (
            <p className="panel-empty-text">No recent impact analysis found.</p>
          )}
        </article>
        <DependencyPanel
          title="Recently Viewed Lineage Graphs"
          items={activity.lineageViews}
          emptyLabel="No lineage graph views yet. Open Lineage Explorer to start."
        />
      </div>
    </section>
  );
}

export default DashboardPage;
