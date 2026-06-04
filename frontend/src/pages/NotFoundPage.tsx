import { Link } from 'react-router-dom';

function NotFoundPage(): JSX.Element {
  return (
    <section className="page-section">
      <div className="state-box state-error" role="alert">
        <h3>Page not found</h3>
        <p>The requested route does not exist in the lineage console.</p>
        <Link className="button-link" to="/dashboard">
          Back to Dashboard
        </Link>
      </div>
    </section>
  );
}

export default NotFoundPage;
