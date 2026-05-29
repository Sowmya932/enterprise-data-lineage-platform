import { useLocation } from 'react-router-dom';

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

  return (
    <header className="app-header">
      <div>
        <p className="header-kicker">Platform Workspace</p>
        <h2>{title}</h2>
      </div>
      <div className="header-meta">
        <span>{new Date().toLocaleDateString()}</span>
      </div>
    </header>
  );
}

export default Header;
