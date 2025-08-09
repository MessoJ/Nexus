import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Film, Home, Newspaper, Rocket } from 'lucide-react'

export const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation()
  const isActive = (path: string) => location.pathname === path
  return (
    <div style={{ fontFamily: 'Inter, ui-sans-serif, system-ui', color: '#0f172a' }}>
      <header style={{ borderBottom: '1px solid #e2e8f0', background: '#ffffff' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 20px', maxWidth: 1200, margin: '0 auto' }}>
          <img src="/logo.png" alt="RelayForge" width={36} height={36} style={{ display: 'block' }} />
          <div style={{ fontWeight: 700, letterSpacing: 0.2 }}>RelayForge</div>
          <nav style={{ marginLeft: 'auto', display: 'flex', gap: 16 }}>
            <NavLink to="/" active={isActive('/')}> <Home size={18}/> Home</NavLink>
            <NavLink to="/jobs" active={isActive('/jobs')}> <Newspaper size={18}/> Jobs</NavLink>
          </nav>
          <a href="https://min.io" target="_blank" rel="noreferrer" style={{ marginLeft: 12, fontSize: 12, color: '#64748b' }}>Storage</a>
        </div>
      </header>
      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 20px' }}>
        {children}
      </main>
      <footer style={{ borderTop: '1px solid #e2e8f0', padding: '12px 20px', fontSize: 12, color: '#64748b' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>© {new Date().getFullYear()} RelayForge</div>
      </footer>
    </div>
  )
}

const NavLink: React.FC<{ to: string; active?: boolean; children: React.ReactNode }> = ({ to, active, children }) => (
  <Link to={to} style={{
    display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 10px', borderRadius: 8,
    textDecoration: 'none', color: active ? '#0f172a' : '#334155', background: active ? '#e2e8f0' : 'transparent'
  }}>
    {children}
  </Link>
)

