import { FormEvent, useState } from 'react';
import ErrorState from '../components/ErrorState';
import LoadingState from '../components/LoadingState';
import { getDownstreamLineage, getUpstreamLineage } from '../services/lineageService';
import type {
  DownstreamLineageResponse,
  RecursiveLineageEdge,
  UpstreamLineageResponse,
} from '../types/api';

type Direction = 'upstream' | 'downstream';

type LineageResult = UpstreamLineageResponse | DownstreamLineageResponse;

function LineageExplorerPage(): JSX.Element {
  const [tableName, setTableName] = useState('');
  const [direction, setDirection] = useState<Direction>('upstream');
  const [maxDepth, setMaxDepth] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<LineageResult | null>(null);

  const handleSubmit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!tableName.trim()) {
      setError('Table name is required.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response =
        direction === 'upstream'
          ? await getUpstreamLineage(tableName.trim(), maxDepth)
          : await getDownstreamLineage(tableName.trim(), maxDepth);
      setResult(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to fetch lineage data';
      setError(message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const relatedTables =
    result == null
      ? []
      : 'upstream_tables' in result
        ? result.upstream_tables
        : result.downstream_tables;

  return (
    <section className="page-section">
      <div className="section-head">
        <h3>Lineage Explorer</h3>
        <p>Trace dependencies recursively with depth control.</p>
      </div>

      <form className="control-form" onSubmit={(event) => void handleSubmit(event)}>
        <label>
          Table Name
          <input
            type="text"
            value={tableName}
            onChange={(event) => setTableName(event.target.value)}
            placeholder="example: mart_sales"
          />
        </label>

        <label>
          Direction
          <select
            value={direction}
            onChange={(event) => setDirection(event.target.value as Direction)}
          >
            <option value="upstream">Upstream</option>
            <option value="downstream">Downstream</option>
          </select>
        </label>

        <label>
          Max Depth
          <input
            type="number"
            min={1}
            max={50}
            value={maxDepth}
            onChange={(event) => setMaxDepth(Number(event.target.value))}
          />
        </label>

        <button type="submit">Explore Lineage</button>
      </form>

      {loading ? <LoadingState label="Computing lineage graph..." /> : null}
      {error ? <ErrorState message={error} /> : null}

      {result ? (
        <div className="panel-grid panel-grid-single">
          <article className="panel">
            <h4>Related Tables ({relatedTables.length})</h4>
            <div className="chip-list">
              {relatedTables.map((table) => (
                <span key={table} className="chip">
                  {table}
                </span>
              ))}
            </div>
          </article>
          <article className="panel">
            <h4>Lineage Chain ({result.total_edges} edges)</h4>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Target</th>
                    <th>Depth</th>
                    <th>DAG</th>
                  </tr>
                </thead>
                <tbody>
                  {result.lineage_chain.map((edge: RecursiveLineageEdge, index: number) => (
                    <tr key={`${edge.source_table}-${edge.target_table}-${index}`}>
                      <td>{edge.source_table}</td>
                      <td>{edge.target_table}</td>
                      <td>{edge.depth}</td>
                      <td>{edge.dag_id ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </div>
      ) : null}
    </section>
  );
}

export default LineageExplorerPage;
