import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import LoadingState from './components/LoadingState';
import AppLayout from './layouts/AppLayout';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const LineageExplorerPage = lazy(() => import('./pages/LineageExplorerPage'));
const ImpactAnalysis = lazy(() => import('./pages/ImpactAnalysis'));
const MetadataSearch = lazy(() => import('./pages/MetadataSearch'));
const DagExplorerPage = lazy(() => import('./pages/DagExplorerPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));

function App(): JSX.Element {
  return (
    <Suspense fallback={<LoadingState label="Loading workspace..." />}>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="lineage" element={<LineageExplorerPage />} />
          <Route path="impact" element={<ImpactAnalysis />} />
          <Route path="search" element={<MetadataSearch />} />
          <Route path="dags" element={<DagExplorerPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}

export default App;
