import { NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { useState } from 'react';
import { api } from './api/client';
import { useApi } from './hooks/useApi';
import Dashboard from './pages/Dashboard';
import DataIntegrity from './pages/DataIntegrity';
import ModelIntegrity from './pages/ModelIntegrity';
import Provenance from './pages/Provenance';
import DistributionShift from './pages/DistributionShift';
import Findings from './pages/Findings';
import AssuranceReport from './pages/AssuranceReport';

const NAV: { to: string; label: string; icon: string; description: string }[] = [
  { to: '/', label: 'Dashboard', icon: 'M3 10.5 12 3l9 7.5M5.5 9v11h13V9M9 20v-6h6v6', description: 'Assurance overview and system health' },
  { to: '/data', label: 'Data Integrity', icon: 'M4 5h16v14H4zM4 9h16M8 5v4M12 5v4M16 5v4', description: 'Inspect datasets and scan evidence' },
  { to: '/model', label: 'Model Integrity', icon: 'M12 3 20 7v10l-8 4-8-4V7zM4 7l8 4 8-4M12 11v10', description: 'Review models, checks, and inference probes' },
  { to: '/provenance', label: 'Provenance', icon: 'M8 7h11v11M16 4l3 3-3 3M16 17H5V6M8 20l-3-3 3-3', description: 'Verify the inference provenance ledger' },
  { to: '/shift', label: 'Distribution Shift', icon: 'M4 19V5M4 19h17M7 15l4-5 3 2 5-7', description: 'Compare reference and current data' },
  { to: '/findings', label: 'Findings', icon: 'M5 4h14v16H5zM8 8h8M8 12h8M8 16h5', description: 'Search findings and manage review dispositions' },
  { to: '/report', label: 'Assurance Report', icon: 'M6 3h9l4 4v14H6zM15 3v5h5M9 12h7M9 16h7', description: 'Generate and export traceable reports' },
];

function NavIcon({ path }: { path: string }) {
  return <svg className="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><path d={path} /></svg>;
}

export default function App() {
  const location = useLocation();
  const [navOpen, setNavOpen] = useState(false);
  const health = useApi(api.health);
  const current = NAV.find((item) => item.to === location.pathname) ?? NAV[0];

  return (
    <div className="app-shell">
      {navOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setNavOpen(false)} />}
      <aside className={`sidebar${navOpen ? ' sidebar-open' : ''}`}>
        <div className="brand">
          <div className="brand-mark" aria-hidden="true"><span>K</span></div>
          <div>
            <div className="brand-name">KavachAI</div>
            <div className="brand-sub">AI Assurance Workbench</div>
          </div>
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav className="nav" aria-label="Primary navigation">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
              onClick={() => setNavOpen(false)}
            >
              <NavIcon path={n.icon} />
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="sidebar-status">
            <span className="status-dot" aria-hidden="true" />
            <div><strong>SYSTEM STATUS</strong><span>{health.loading ? 'Checking connection' : health.data?.status === 'ok' ? 'Backend connected' : 'Backend unavailable'}</span></div>
            <button className="status-refresh" onClick={health.reload} aria-label="Refresh backend status" title="Refresh backend status">↻</button>
          </div>
          <div className="proto-tag">LOCAL PROTOTYPE</div>
          <div className="foot-note">Offline workbench. All results are measured by the backend; unevaluated modules are labeled as such.</div>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setNavOpen(true)} aria-label="Open navigation" aria-expanded={navOpen}>
            <span /><span /><span />
          </button>
          <div className="topbar-title">
            <span className="topbar-eyebrow">KAVACHAI / ASSURANCE WORKSPACE</span>
            <strong>{current.label}</strong>
            <span>{current.description}</span>
          </div>
          <div className="topbar-meta">
            <span className={`connection-pill${health.data?.status === 'ok' ? ' connected' : ''}`} role="status">
              <span className="status-dot" />{health.loading ? 'Connecting' : health.data?.status === 'ok' ? 'Backend connected' : 'Backend offline'}
            </span>
            <span className="user-chip" aria-label="Local prototype workspace"><span>KA</span><b>Local</b></span>
          </div>
        </header>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/data" element={<DataIntegrity />} />
          <Route path="/model" element={<ModelIntegrity />} />
          <Route path="/provenance" element={<Provenance />} />
          <Route path="/shift" element={<DistributionShift />} />
          <Route path="/findings" element={<Findings />} />
          <Route path="/report" element={<AssuranceReport />} />
        </Routes>
      </main>
    </div>
  );
}
