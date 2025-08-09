import React from 'react'
import { Rocket, PlayCircle, Workflow, PanelsTopLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

export const Landing: React.FC = () => {
  return (
    <div>
      <section style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 24, alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 36, lineHeight: 1.2, marginBottom: 12 }}>Automate content from idea to publish</h1>
          <p style={{ color: '#475569', marginBottom: 16 }}>RelayForge ingests sources, drafts with AI, generates media, and distributes—review anytime.</p>
          <div style={{ display: 'flex', gap: 12 }}>
            <Link to="/jobs" style={primaryBtn}>Open Jobs</Link>
            <a href="http://localhost:15672" style={ghostBtn}>Queue Monitor</a>
          </div>
        </div>
        <div style={{ justifySelf: 'end' }}>
          <img src="/logo.png" alt="RelayForge" width={160} height={160} />
        </div>
      </section>

      <section style={{ marginTop: 32, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        <Feature icon={<PanelsTopLeft size={18}/>} title="Ingest">
          Pull from feeds and APIs.
        </Feature>
        <Feature icon={<Workflow size={18}/>} title="Analyze">
          LLM turns news into scripts.
        </Feature>
        <Feature icon={<PlayCircle size={18}/>} title="Produce">
          Generate audio/video assets.
        </Feature>
        <Feature icon={<Rocket size={18}/>} title="Distribute">
          Approve and publish everywhere.
        </Feature>
      </section>
    </div>
  )
}

const primaryBtn: React.CSSProperties = { background: '#0f172a', color: '#fff', padding: '10px 14px', borderRadius: 8, textDecoration: 'none' }
const ghostBtn: React.CSSProperties = { background: '#e2e8f0', color: '#0f172a', padding: '10px 14px', borderRadius: 8, textDecoration: 'none' }

const card: React.CSSProperties = { border: '1px solid #e2e8f0', borderRadius: 10, padding: 12, background: '#fff' }

const Feature: React.FC<{ icon: React.ReactNode, title: string, children: React.ReactNode }> = ({ icon, title, children }) => (
  <div style={card}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600 }}>
      {icon} {title}
    </div>
    <div style={{ color: '#475569', fontSize: 14, marginTop: 6 }}>{children}</div>
  </div>
)

