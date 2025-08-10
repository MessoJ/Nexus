import React from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { BrowserRouter as Router } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import App from './App';
import './index.css';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

const container = document.getElementById('root')!;
const root = createRoot(container);

root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <Router>
        <App />
        <Toaster position="top-right" />
      </Router>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </React.StrictMode>
);
      <header style={{ borderBottom: '1px solid #ddd', paddingBottom: '20px', marginBottom: '20px' }}>
        <h1 style={{ margin: 0, color: '#333' }}>🚀 Nexus Dashboard</h1>
        <p style={{ color: '#666', margin: '5px 0 0 0' }}>AI-Powered Content Pipeline</p>
      </header>
      
      <div style={{ display: 'grid', gap: '20px', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
        <div style={{ padding: '20px', border: '1px solid #ddd', borderRadius: '8px' }}>
          <h3>📊 System Status</h3>
          <p style={{ color: 'green' }}>✅ All services running</p>
          <p>🌾 Harvester: Active</p>
          <p>🧠 Analyst: Ready</p>
          <p>🎬 Producer: Ready</p>
          <p>📡 Distributor: Ready</p>
        </div>
        
        <div style={{ padding: '20px', border: '1px solid #ddd', borderRadius: '8px' }}>
          <h3>🔗 Quick Links</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <a href="http://localhost:8000/health" target="_blank" style={{ color: '#0066cc' }}>API Health Check</a>
            <a href="http://localhost:15672" target="_blank" style={{ color: '#0066cc' }}>RabbitMQ Management</a>
            <a href="http://localhost:9001" target="_blank" style={{ color: '#0066cc' }}>MinIO Console</a>
          </div>
        </div>
      </div>

      <div style={{ marginTop: '30px' }}>
        <h3>📋 Content Jobs</h3>
        {loading ? (
          <p>Loading jobs...</p>
        ) : (
          <div style={{ border: '1px solid #ddd', borderRadius: '8px', overflow: 'hidden' }}>
            {jobs.length === 0 ? (
              <p style={{ padding: '20px', margin: 0, color: '#666' }}>
                No jobs yet. The harvester will start collecting content automatically.
              </p>
            ) : (
              jobs.map((job, i) => (
                <div key={i} style={{ 
                  padding: '15px', 
                  borderBottom: i < jobs.length - 1 ? '1px solid #eee' : 'none',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <div>
                    <strong>{job.title || 'Untitled'}</strong>
                    <div style={{ fontSize: '14px', color: '#666' }}>Status: {job.status}</div>
                  </div>
                  <div style={{ fontSize: '12px', color: '#999' }}>
                    ID: {job.id}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}

const container = document.getElementById('root')!
createRoot(container).render(
  <React.StrictMode>
    <Dashboard />
  </React.StrictMode>
)

