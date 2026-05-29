import { useEffect, useState } from 'react';
import ErrorState from '../components/ErrorState';
import LoadingState from '../components/LoadingState';
import { getMetadata } from '../services/metadataService';
import type { MetadataResponse } from '../types/api';

function DagExplorerPage(): JSX.Element {
  const [metadata, setMetadata] = useState<MetadataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDagData = async (): Promise<void> => {
    setLoading(true);
    setError(null);

    try {
      const response = await getMetadata();
      setMetadata(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load DAG metadata';
      setError(message);
      setMetadata(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDagData();
  }, []);

  if (loading) {
    return <LoadingState label="Loading DAG inventory..." />;
  }

  if (error || !metadata) {
    return <ErrorState message={error ?? 'No DAG metadata found.'} onRetry={loadDagData} />;
  }

  return (
    <section className="page-section">
      <div className="section-head">
        <h3>DAG Explorer</h3>
        <p>Inspect orchestrated workflows and task-level dependency metadata.</p>
      </div>

      <div className="panel-grid panel-grid-single">
        <article className="panel">
          <h4>DAGs ({metadata.dags.length})</h4>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>DAG ID</th>
                  <th>Task Count</th>
                </tr>
              </thead>
              <tbody>
                {metadata.dags.map((dag) => (
                  <tr key={dag.id}>
                    <td>{dag.dag_id}</td>
                    <td>{dag.tasks?.length ?? dag.task_count ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel">
          <h4>Task Dependencies ({metadata.dependencies.task_edges.length})</h4>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Upstream Task</th>
                  <th>Downstream Task</th>
                </tr>
              </thead>
              <tbody>
                {metadata.dependencies.task_edges.map((edge) => (
                  <tr key={edge.id}>
                    <td>{edge.upstream_task}</td>
                    <td>{edge.downstream_task}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </div>
    </section>
  );
}

export default DagExplorerPage;
