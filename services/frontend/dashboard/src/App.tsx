import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Dashboard from './pages/DashboardFunctional';
import JobDetails from './pages/JobDetails';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import TestComponent from './components/TestComponent';

function App() {
  return (
    <ErrorBoundary>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/jobs" element={<Dashboard />} />
          <Route path="/jobs/:jobId" element={<JobDetails />} />
        </Routes>
      </Layout>
    </ErrorBoundary>
  );
}

export default App;
