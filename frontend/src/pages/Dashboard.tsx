import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Finding } from '../api/types';
import { api } from '../api/client';
import { useApi, useAsyncAction } from '../hooks/useApi';
import StatusBadge from '../components/StatusBadge';

type ModuleStatus = 'ok' | 'review' | 'quarantine' | 'not-evaluated';

const MODULES = [
  { key: 'data', label: 'Data Integrity', link: '/data' },
  { key: 'model', label: 'Model Integrity', link: '/model' },
  { key: 'provenance', label: 'Provenance', link: '/provenance' },
  { key: 'shift', label: 'Distribution Shift', link: '/shift' },
];

function isOpen(f: Finding): boolean {
  // System disposition doubles as review state: ACCEPT = closed,
  // REVIEW / QUARANTINE = still needs attention.
  const d = (f.disposition ?? 'REVIEW').trim().toUpperCase();
  return d !== 'ACCEPT';
}

function moduleStatus(findings: Finding[], category: string): ModuleStatus {
  const rel = findings.filter((f) => f.category.trim().toLowerCase() === category);
  if (rel.length === 0) return 'not-evaluated';
  const open = rel.filter(isOpen);
  if (open.length === 0) return 'ok';
  const severe = open.some((f) => ['critical', 'high'].includes(f.severity.trim().toLowerCase()));
  return severe ? 'quarantine' : 'review';
}

const STATUS_LABEL: Record<ModuleStatus, string> = {
  ok: 'OK',
  review: 'REVIEW',
  quarantine: 'QUARANTINE',
  'not-evaluated': 'Not evaluated yet',
};

export default function Dashboard() {
  const navigate = useNavigate();
  const health = useApi(api.health);
  const findingsApi = useApi(api.listFindings);
  const demo = useAsyncAction(api.runDemo);
  const [seed, setSeed] = useState(42);
  const [elapsed, setElapsed] = useState(0);
  const [result, setResult] = useState<import('../api/types').DemoRunResult | null>(null);

  useEffect(() => {
    if (!demo.loading) return;
    const t = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(t);
  }, [demo.loading]);

  const findings = useMemo(() => findingsApi.data ?? [], [findingsApi.data]);
  const openCount = findings.filter(isOpen).length;
  const recent = useMemo(
    () =>
      [...findings]
        .sort((a, b) => String(b.created_at ?? '').localeCompare(String(a.created_at ?? '')))
        .slice(0, 5),
    [findings],
  );

  const runDemo = async () => {
    setResult(null);
    setElapsed(0);
    const r = await demo.run(seed);
    if (r) setResult(r);
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Assurance Dashboard</h1>
        <p className="page-sub">
          Per-module assurance status derived from recorded findings. No single trust score is computed —
          each module reports its own measured state.
        </p>
      </div>

      <div className="card">
        <div className="card-title">Backend</div>
        {health.loading && <div className="spinner">Checking backend health…</div>}
        {health.error && <div className="alert alert-error">Backend unreachable: {health.error}</div>}
        {health.data && (
          <dl className="kv">
            <dt>Status</dt><dd><StatusBadge status={health.data.status} /></dd>
            <dt>Version</dt><dd className="mono">{health.data.version}</dd>
            <dt>Database</dt><dd>{health.data.db_ok ? 'reachable' : 'unreachable'}</dd>
            <dt>Mode</dt><dd>{health.data.offline ? 'offline (no external calls)' : 'unknown'}</dd>
          </dl>
        )}
      </div>

      <div className="card">
        <div className="card-title">Module status</div>
        {findingsApi.loading && <div className="spinner">Loading findings…</div>}
        {findingsApi.error && <div className="alert alert-error">{findingsApi.error}</div>}
        {!findingsApi.loading && !findingsApi.error && (
          <div className="card-grid">
            {MODULES.map((m) => {
              const st = moduleStatus(findings, m.key);
              return (
                <div key={m.key} className="stat-card">
                  <div className="stat-label">{m.label}</div>
                  <div style={{ margin: '8px 0' }}>
                    <StatusBadge status={STATUS_LABEL[st]} />
                  </div>
                  <div className="stat-note">
                    {st === 'not-evaluated'
                      ? 'No findings recorded for this module yet.'
                      : `${findings.filter((f) => f.category.trim().toLowerCase() === m.key && isOpen(f)).length} open finding(s)`}
                  </div>
                  <div style={{ marginTop: 10 }}>
                    <button className="btn btn-secondary btn-sm" onClick={() => navigate(m.link)}>
                      Open module
                    </button>
                  </div>
                </div>
              );
            })}
            <div className="stat-card">
              <div className="stat-label">Open findings</div>
              <div className="stat-value">{openCount}</div>
              <div className="stat-note">Across all modules</div>
              <div style={{ marginTop: 10 }}>
                <button className="btn btn-secondary btn-sm" onClick={() => navigate('/findings')}>
                  Review findings
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">One-click demo</div>
        <p className="section-text" style={{ color: '#5d6f84' }}>
          Runs the 15-step demo script server-side (clean baseline → controlled synthetic attacks →
          scans → model checks → inference → provenance → shift → report). All demo data is synthetic
          and seeded.
        </p>
        <div className="form-row">
          <div className="field">
            <label htmlFor="seed">Seed</label>
            <input
              id="seed"
              className="input"
              type="number"
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
              style={{ minWidth: 120 }}
            />
          </div>
          <button className="btn btn-primary" onClick={runDemo} disabled={demo.loading}>
            {demo.loading ? 'Running demo…' : 'RUN DEMO'}
          </button>
        </div>
        {demo.loading && (
          <div>
            <div className="spinner">Demo running on the backend — step results appear when the script completes ({elapsed}s elapsed).</div>
            <div className="progress-line"><div /></div>
          </div>
        )}
        {demo.error && <div className="alert alert-error">{demo.error}</div>}
        {result && (
          <div>
            <dl className="kv" style={{ marginBottom: 12 }}>
              <dt>Experiment</dt><dd className="mono">{result.experiment_id}</dd>
              <dt>Report</dt>
              <dd>
                <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/report?report_id=${encodeURIComponent(result.report_id)}`)}>
                  Open report {result.report_id}
                </button>
              </dd>
            </dl>
            <div className="table-wrap">
              <table className="table steps-table">
                <thead><tr><th>Step</th><th>OK</th><th>Time (ms)</th></tr></thead>
                <tbody>
                  {result.steps.map((s, i) => (
                    <tr key={i}>
                      <td>{s.name}</td>
                      <td>{s.ok ? <span className="ok-yes">yes</span> : <span className="ok-no">no</span>}</td>
                      <td className="mono">{s.ms}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="btn-row" style={{ marginTop: 12 }}>
              <button className="btn btn-secondary" onClick={() => { findingsApi.reload(); }}>
                Refresh findings
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">Recent findings</div>
        {findingsApi.loading && <div className="spinner">Loading…</div>}
        {!findingsApi.loading && recent.length === 0 && (
          <div className="empty-state"><div className="big">No findings yet</div>Run a scan or the demo to generate findings.</div>
        )}
        {recent.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Title</th><th>Category</th><th>Severity</th><th>Disposition</th></tr></thead>
              <tbody>
                {recent.map((f) => (
                  <tr key={f.id}>
                    <td>{f.title}</td>
                    <td><StatusBadge status={f.category} /></td>
                    <td><StatusBadge status={f.severity} /></td>
                    <td><StatusBadge status={f.disposition ?? 'REVIEW'} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
