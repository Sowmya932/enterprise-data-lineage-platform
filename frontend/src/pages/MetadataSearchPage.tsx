import { FormEvent, useState } from 'react';
import ErrorState from '../components/ErrorState';
import LoadingState from '../components/LoadingState';
import {
  searchColumns,
  searchDags,
  searchLineageRelationships,
  searchTables,
} from '../services/searchService';
import type {
  ColumnRecord,
  DagRecord,
  LineageRelationship,
  SearchResponse,
  TableRecord,
} from '../types/api';

type SearchEntity = 'tables' | 'columns' | 'dags' | 'lineage';
type SearchResults =
  | SearchResponse<TableRecord>
  | SearchResponse<ColumnRecord>
  | SearchResponse<DagRecord>
  | SearchResponse<LineageRelationship>;

function MetadataSearchPage(): JSX.Element {
  const [entity, setEntity] = useState<SearchEntity>('tables');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<SearchResults | null>(null);

  const handleSearch = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!query.trim()) {
      setError('Search query is required.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      let response: SearchResults;
      if (entity === 'tables') {
        response = await searchTables({ query: query.trim() });
      } else if (entity === 'columns') {
        response = await searchColumns({ query: query.trim() });
      } else if (entity === 'dags') {
        response = await searchDags({ query: query.trim() });
      } else {
        response = await searchLineageRelationships({ query: query.trim() });
      }

      setResults(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Search failed';
      setError(message);
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="page-section">
      <div className="section-head">
        <h3>Metadata Search</h3>
        <p>Search tables, columns, DAGs, and lineage relationships from one interface.</p>
      </div>

      <form className="control-form" onSubmit={(event) => void handleSearch(event)}>
        <label>
          Entity Type
          <select value={entity} onChange={(event) => setEntity(event.target.value as SearchEntity)}>
            <option value="tables">Tables</option>
            <option value="columns">Columns</option>
            <option value="dags">DAGs</option>
            <option value="lineage">Lineage Relationships</option>
          </select>
        </label>

        <label>
          Search Query
          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search metadata"
          />
        </label>

        <button type="submit">Search</button>
      </form>

      {loading ? <LoadingState label="Searching metadata..." /> : null}
      {error ? <ErrorState message={error} /> : null}

      {results ? (
        <article className="panel">
          <h4>Results ({results.pagination.total})</h4>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody>
                {results.items.map((item, index) => {
                  if ('dag_id' in item) {
                    return (
                      <tr key={`${item.dag_id}-${index}`}>
                        <td>{item.dag_id}</td>
                        <td>DAG</td>
                      </tr>
                    );
                  }

                  if ('source_table' in item && 'target_table' in item) {
                    return (
                      <tr key={`${item.source_table}-${item.target_table}-${index}`}>
                        <td>
                          {item.source_table} {'->'} {item.target_table}
                        </td>
                        <td>Lineage Relationship</td>
                      </tr>
                    );
                  }

                  if ('table_id' in item) {
                    return (
                      <tr key={`${item.table_id}-${item.name}-${index}`}>
                        <td>{item.name}</td>
                        <td>Column</td>
                      </tr>
                    );
                  }

                  return (
                    <tr key={`${item.id}-${index}`}>
                      <td>{item.name}</td>
                      <td>Table</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </article>
      ) : null}
    </section>
  );
}

export default MetadataSearchPage;
