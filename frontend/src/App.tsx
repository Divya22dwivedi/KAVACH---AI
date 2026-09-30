import { NavLink, Route, Routes } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import DataIntegrity from './pages/DataIntegrity';
import ModelIntegrity from './pages/ModelIntegrity';
import Provenance from './pages/Provenance';
import DistributionShift from './pages/DistributionShift';
import Findings from './pages/Findings';
import AssuranceReport from './pages/AssuranceReport';

const NAV: { to: string; label: string }[] = [
  { to: '/', label: 'Dashboard' },
  { to: '/data', label: 'Data Integrity' },
  { to: '/model', label: 'Model Integrity' },
  { to: '/provenance', label: 'Provenance' },
  { to: '/shift', label: 'Distribution Shift' },
  { to: '/findings', label: 'Findings' },
  { to: '/report', label: 'Assurance Report' },
];

export default function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">K</div>
          <div>
            <div className="brand-name">KavachAI</div>
            <div className="brand-sub">AI Assurance Workbench</div>
          </div>
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="proto-tag">PROTOTYPE</div>
          <div className="foot-note">Offline workbench. All results are measured by the backend; unevaluated modules are labeled as such.</div>
        </div>
      </aside>
      <main className="main">
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
