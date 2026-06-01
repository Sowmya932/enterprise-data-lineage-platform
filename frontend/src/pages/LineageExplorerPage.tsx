import LineageGraph from '../components/LineageGraph';

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
      <LineageGraph />
    </section>
  );
}

export default LineageExplorerPage;
