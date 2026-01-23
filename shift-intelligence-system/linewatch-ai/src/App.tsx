
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import DashboardPage from './pages/DashboardPage';

// PERFORMANCE: Lazy load Analytics page (only loads when navigating to /analytics)
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'));

/**
 * Main App Router.
 * 
 * /          -> Main Simulation Dashboard
 * /analytics -> Scientific Experiment Analytics (New Tab, lazy loaded)
 */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route 
          path="/analytics" 
          element={
            <Suspense fallback={<div style={{padding: '2rem', color: '#fff'}}>Loading Analytics...</div>}>
              <AnalyticsPage />
            </Suspense>
          } 
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
