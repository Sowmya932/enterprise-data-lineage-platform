import { NavLink } from 'react-router-dom';

const navItems = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/lineage', label: 'Lineage Explorer' },
  { to: '/impact', label: 'Impact Analysis' },
  { to: '/search', label: 'Metadata Search' },
  { to: '/dags', label: 'DAG Explorer' },
];

function Sidebar(): JSX.Element {
  return (
    <aside className="sidebar">
      <div className="brand-block">
        <p className="brand-kicker">Enterprise Data</p>
        <h1>Lineage Console</h1>
      </div>
      <nav className="side-nav" aria-label="Primary">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              isActive ? 'side-link side-link-active' : 'side-link'
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;
