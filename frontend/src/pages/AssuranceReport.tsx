import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { useApi, useAsyncAction } from '../hooks/useApi';

function renderValue(v: unknown): React.ReactNode {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (Array.isArray(v)) {
    return (
      <ul style={{ margin: '4px 0', paddingLeft: 18 }}>
        {v.slice(0, 12).map((item, i) => (
          <li key={i}>{typeof item === 'object' ? JSON.stringify(item) : String(item)}</li>
        ))}
        {v.length > 12 && <li>… and {v.length - 12} more</li>}
      </ul>
    );
  }
  return (
    <dl className="kv">
      {Object.entries(v as Record<string, unknown>).map(([k, val]) => (
        <div key={k} style={{ display: 'contents' }}>
          <dt>{k}</dt>
          <dd className="mono" style={{ whiteSpace: 'pre-wrap' }}>
            {typeof val === 'object' ? JSON.stringify(val, null, 2) : String(val ?? '—')}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export default function AssuranceReport() {
  const [params] = useSearchParams();
  const [experimentId, setExperimentId] = useState(params.get('report_id') ?? params.get('experiment_id') ?? '');
  const generate = useAsyncAction(api.generateReport);
  const [reportId, setReportId] = useState<string | null>(params.get('report_id'));

  const preview = useApi(() => (reportId ? api.reportJson(reportId) : Promise.resolve(null)), [reportId]);

  const doGenerate = async () => {
    if (!experimentId) return;
    const r = await generate.run(experimentId);
    if (r) setReportId(r.report_id);
  };

  const sections: [string, unknown][] =
    preview.data && typeof preview.data === 'object'
      ? Object.entries(preview.data as Record<string, unknown>)
      : [];

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Assurance Report</h1>
        <p className="page-sub">
          Generate the assurance report for an experiment: findings, evidence, limitations and
          untested areas. Download as JSON or PDF.
        </p>
      </div>

      <div className="card">
        <div className="card-title">Generate</div>
        <div className="form-row">
          <div className="field" style={{ flex: 1, minWidth: 260 }}>
            <label htmlFor="exp">Experiment ID</label>
            <input
              id="exp"
              className="input"
              value={experimentId}
              onChange={(e) => setExperimentId(e.target.value)}
              placeholder="e.g. exp_20260930_0137 (from a scan or the demo)"
            />
          </div>
          <button className="btn btn-primary" onClick={doGenerate} disabled={generate.loading || !experimentId}>
            {generate.loading ? 'Generating…' : 'Generate report'}
          </button>
        </div>
        {generate.error && <div className="alert alert-error">{generate.error}</div>}
        {reportId && (
          <div className="btn-row" style={{ marginTop: 6 }}>
            <span style={{ fontSize: 13, color: '#5d6f84' }}>
              Report <span className="mono">{reportId}</span>
            </span>
            <a className="btn btn-secondary" href={api.reportJsonUrl(reportId)} download>
              Download JSON
            </a>
            <a className="btn btn-secondary" href={api.reportPdfUrl(reportId)} download>
              Download PDF
            </a>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">Section preview</div>
        {!reportId && (
          <div className="empty-state"><div className="big">No report yet</div>Generate a report to preview its sections here.</div>
        )}
        {reportId && preview.loading && <div className="spinner">Loading report JSON…</div>}
        {reportId && preview.error && <div className="alert alert-error">{preview.error}</div>}
        {reportId && !preview.loading && !preview.error && sections.length === 0 && (
          <div className="empty-state"><div className="big">Empty report</div>The backend returned no sections.</div>
        )}
        {sections.map(([name, value], i) => (
          <div key={name} style={{ marginBottom: 18 }}>
            <h3 className="chart-title">
              {i + 1}. {name}
            </h3>
            <div style={{ fontSize: 13 }}>{renderValue(value)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
