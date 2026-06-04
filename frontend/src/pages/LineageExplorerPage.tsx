import { Suspense, lazy } from 'react';
import LoadingState from '../components/LoadingState';

const LineageGraph = lazy(() => import('../components/LineageGraph'));

function LineageExplorerPage(): JSX.Element {
  return (
    <section className="page-section">
      <div className="section-head">
        <h3>Interactive Lineage Explorer</h3>
        <p>
          Explore table, column, and DAG dependencies with zoom, pan, search, and
          click-driven lineage expansion.
        </p>
      </div>
      <Suspense fallback={<LoadingState label="Loading lineage explorer..." />}>
        <LineageGraph />
      </Suspense>
    </section>
  );
}

export default LineageExplorerPage;
