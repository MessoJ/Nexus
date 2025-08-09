import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { CheckCircle2, ExternalLink, RefreshCw } from 'lucide-react'

type Job = {
  id: string
  title?: string
  status: string
  media_url?: string
}

const API_BASE = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000'

export const Jobs: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(false)

  const refresh = async () => {
    setLoading(true)
    try {
      const { data } = await axios.get(`${API_BASE}/jobs`)
      setJobs(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 10000)
    return () => clearInterval(id)
  }, [])

  const approve = async (jobId: string) => {
    await axios.post(`${API_BASE}/jobs/${jobId}/approve`)
    await refresh()
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Jobs</h2>
        <button onClick={refresh} disabled={loading} style={iconBtn}>
          <RefreshCw size={16}/> {loading ? 'Refreshing' : 'Refresh'}
        </button>
      </div>
      <div style={{ display: 'grid', gap: 12 }}>
        {jobs.map(j => (
          <div key={j.id} style={rowCard}>
            <div>
              <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 680 }} title={j.title || ''}>
                {j.title || '(untitled)'}
              </div>
              <div style={{ fontSize: 12, color: '#64748b' }}>Status: {j.status}</div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {j.media_url && (
                <a href={j.media_url} target="_blank" rel="noreferrer" style={iconBtn}><ExternalLink size={16}/> Open</a>
              )}
              <button onClick={() => approve(j.id)} disabled={j.status === 'published'} style={primaryBtn}>
                <CheckCircle2 size={16}/> Approve & Post
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

const rowCard: React.CSSProperties = { border: '1px solid #e2e8f0', borderRadius: 10, padding: 12, background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }
const primaryBtn: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 6, background: '#0f172a', color: '#fff', padding: '8px 12px', borderRadius: 8, border: 'none' }
const iconBtn: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 6, background: '#e2e8f0', color: '#0f172a', padding: '8px 12px', borderRadius: 8, border: 'none', textDecoration: 'none' }

