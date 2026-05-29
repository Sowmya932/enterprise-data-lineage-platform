import { Navigate, Route, Routes } from 'react-router-dom';
import AppLayout from './layouts/AppLayout';
import DashboardPage from './pages/DashboardPage';
import LineageExplorerPage from './pages/LineageExplorerPage';
import ImpactAnalysisPage from './pages/ImpactAnalysisPage';
import MetadataSearchPage from './pages/MetadataSearchPage';
import DagExplorerPage from './pages/DagExplorerPage';

function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="lineage" element={<LineageExplorerPage />} />
        <Route path="impact" element={<ImpactAnalysisPage />} />
        <Route path="search" element={<MetadataSearchPage />} />
        <Route path="dags" element={<DagExplorerPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;
