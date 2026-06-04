import { Link, useLocation } from 'react-router-dom';

const routeTitleMap: Record<string, string> = {
  '/dashboard': 'System Overview',
  '/lineage': 'Lineage Explorer',
  '/impact': 'Impact Analysis',
  '/search': 'Metadata Search',
  '/dags': 'DAG Explorer',
};

function Header(): JSX.Element {
  const location = useLocation();
  const title = routeTitleMap[location.pathname] ?? 'Enterprise Lineage Platform';
  const pathParts = location.pathname.split('/').filter(Boolean);
  const crumbs = pathParts.map((part, index) => {
    const path = `/${pathParts.slice(0, index + 1).join('/')}`;
    const label = routeTitleMap[path] ?? part.replace(/-/g, ' ');
    return { path, label };
  });

  return (
    <header className="app-header">
      <div>
        <p className="header-kicker">Platform Workspace</p>
        <h2>{title}</h2>
        <nav className="breadcrumbs" aria-label="Breadcrumb">
          <Link to="/dashboard">Home</Link>
          {crumbs.map((crumb) => (
            <span key={crumb.path}>
              <span>/</span>
              <Link to={crumb.path}>{crumb.label}</Link>
            </span>
          ))}
        </nav>
      </div>
      <div className="header-meta">
        <span>{new Date().toLocaleDateString()}</span>
      </div>
    </header>
  );
}

export default Header;
