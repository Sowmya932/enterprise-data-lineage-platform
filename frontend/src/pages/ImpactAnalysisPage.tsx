import { FormEvent, useState } from 'react';
import ErrorState from '../components/ErrorState';
import LoadingState from '../components/LoadingState';
import { analyzeColumnImpact, analyzeTableImpact } from '../services/impactService';
import type { ColumnImpactResponse, TableImpactResponse } from '../types/api';

type ImpactMode = 'table' | 'column';

function ImpactAnalysisPage(): JSX.Element {
  const [mode, setMode] = useState<ImpactMode>('table');
  const [tableName, setTableName] = useState('');
  const [columnName, setColumnName] = useState('');
  const [maxDepth, setMaxDepth] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tableResult, setTableResult] = useState<TableImpactResponse | null>(null);
  const [columnResult, setColumnResult] = useState<ColumnImpactResponse | null>(null);

  const handleSubmit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();

    if (mode === 'table' && !tableName.trim()) {
      setError('Table name is required for table impact analysis.');
      return;
    }

    if (mode === 'column' && !columnName.trim()) {
      setError('Column name is required for column impact analysis.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      if (mode === 'table') {
        const response = await analyzeTableImpact(tableName.trim(), maxDepth);
        setTableResult(response);
        setColumnResult(null);
      } else {
        const response = await analyzeColumnImpact(columnName.trim(), {
          table: tableName.trim() || undefined,
          maxDepth,
        });
        setColumnResult(response);
        setTableResult(null);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Impact analysis request failed';
      setError(message);
      setTableResult(null);
      setColumnResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="page-section">
      <div className="section-head">
        <h3>Impact Analysis</h3>
        <p>Estimate blast radius before schema or pipeline changes.</p>
      </div>

      <form className="control-form" onSubmit={(event) => void handleSubmit(event)}>
        <label>
          Mode
          <select value={mode} onChange={(event) => setMode(event.target.value as ImpactMode)}>
            <option value="table">Table Impact</option>
            <option value="column">Column Impact</option>
          </select>
        </label>

        <label>
          Table Name {mode === 'column' ? '(Optional scope)' : ''}
          <input
            type="text"
            value={tableName}
            onChange={(event) => setTableName(event.target.value)}
            placeholder="example: mart_sales"
          />
        </label>

        {mode === 'column' ? (
          <label>
            Column Name
            <input
              type="text"
              value={columnName}
              onChange={(event) => setColumnName(event.target.value)}
              placeholder="example: revenue"
            />
          </label>
        ) : null}

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

        <button type="submit">Analyze Impact</button>
      </form>

      {loading ? <LoadingState label="Calculating impact graph..." /> : null}
      {error ? <ErrorState message={error} /> : null}

      {tableResult ? (
        <article className="panel">
          <h4>Table Impact Result</h4>
          <p className="severity">Severity: {tableResult.severity}</p>
          <p>Affected Tables: {tableResult.affected_tables.length}</p>
          <p>Impacted DAGs: {tableResult.impacted_dags.length}</p>
        </article>
      ) : null}

      {columnResult ? (
        <article className="panel">
          <h4>Column Impact Result</h4>
          <p className="severity">Severity: {columnResult.severity}</p>
          <p>Affected Tables: {columnResult.affected_tables.length}</p>
          <p>Affected Columns: {columnResult.affected_columns.length}</p>
          <p>Impacted DAGs: {columnResult.impacted_dags.length}</p>
        </article>
      ) : null}
    </section>
  );
}

export default ImpactAnalysisPage;
