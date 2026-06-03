import { Navigate, Route, Routes } from 'react-router-dom';
import AppLayout from './layouts/AppLayout';
import DashboardPage from './pages/DashboardPage';
import LineageExplorerPage from './pages/LineageExplorerPage';
import ImpactAnalysis from './pages/ImpactAnalysis';
import MetadataSearch from './pages/MetadataSearch';
import DagExplorerPage from './pages/DagExplorerPage';

function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="lineage" element={<LineageExplorerPage />} />
        <Route path="impact" element={<ImpactAnalysis />} />
        <Route path="search" element={<MetadataSearch />} />
        <Route path="dags" element={<DagExplorerPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;
