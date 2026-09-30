import type { Finding } from '../api/types';
import StatusBadge from './StatusBadge';

export const CATEGORIES = ['all', 'data', 'model', 'provenance', 'shift'] as const;
export const SEVERITIES = ['all', 'critical', 'high', 'medium', 'low', 'info'] as const;

interface Props {
  findings: Finding[];
  category: string;
  severity: string;
  onCategory: (c: string) => void;
  onSeverity: (s: string) => void;
  onOpen: (f: Finding) => void;
}

/** Filterable findings table with category tabs + severity filter. */
export default function FindingTable({ findings, category, severity, onCategory, onSeverity, onOpen }: Props) {
  return (
    <div>
      <div className="form-row" style={{ justifyContent: 'space-between' }}>
        <div className="tabs">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              className={`tab${category === c ? ' active' : ''}`}
              onClick={() => onCategory(c)}
            >
              {c === 'all' ? 'All' : c.charAt(0).toUpperCase() + c.slice(1)}
            </button>
          ))}
        </div>
        <div className="field">
          <label htmlFor="sev">Severity</label>
          <select id="sev" className="select" value={severity} onChange={(e) => onSeverity(e.target.value)}>
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>{s === 'all' ? 'All severities' : s}</option>
            ))}
          </select>
        </div>
      </div>

      {findings.length === 0 ? (
        <div className="empty-state">
          <div className="big">No findings match</div>
          No findings recorded for this filter yet — run a scan, model checks, or the demo.
        </div>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Category</th>
                <th>Severity</th>
                <th>Disposition</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f) => (
                <tr
                  key={f.id}
                  className="clickable"
                  tabIndex={0}
                  role="button"
                  aria-label={`Open finding: ${f.title}`}
                  onClick={() => onOpen(f)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      onOpen(f);
                    }
                  }}
                >
                  <td>{f.title}</td>
                  <td><StatusBadge status={f.category} /></td>
                  <td><StatusBadge status={f.severity} /></td>
                  <td><StatusBadge status={f.disposition ?? 'REVIEW'} /></td>
                  <td>{f.created_at ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
