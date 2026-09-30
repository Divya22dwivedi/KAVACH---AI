import { useEffect, useState } from 'react';
import type { Finding } from '../api/types';
import { api } from '../api/client';
import { useAsyncAction } from '../hooks/useApi';
import StatusBadge from './StatusBadge';

interface Props {
  finding: Finding | null;
  onClose: () => void;
  onSaved: (updated: Finding) => void;
}

const DISPOSITIONS = ['ACCEPT', 'REVIEW', 'QUARANTINE'];

function fmt(v: unknown): string {
  if (v === null || v === undefined || v === '') return 'Not reported';
  if (typeof v === 'object') return JSON.stringify(v, null, 2);
  return String(v);
}

/**
 * Finding detail drawer: method / evidence / confidence / severity /
 * limitations / disposition + reviewer override (PATCH).
 */
export default function EvidenceDrawer({ finding, onClose, onSaved }: Props) {
  const [disposition, setDisposition] = useState<string>(finding?.disposition ?? 'REVIEW');
  const [reviewerNote, setReviewerNote] = useState<string>(finding?.reviewer_note ?? '');
  const save = useAsyncAction(api.patchFinding);

  useEffect(() => {
    setDisposition(finding?.disposition ?? 'REVIEW');
    setReviewerNote(finding?.reviewer_note ?? '');
  }, [finding]);

  useEffect(() => {
    if (!finding) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [finding, onClose]);

  if (!finding) return null;

  const handleSave = async () => {
    const updated = await save.run(finding.id, { disposition, reviewer_note: reviewerNote });
    if (updated) onSaved(updated);
  };

  return (
    <>
      <button className="drawer-overlay" onClick={onClose} aria-label="Close finding details" />
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="finding-drawer-title">
        <div className="drawer-head">
          <div>
            <h2 className="drawer-title" id="finding-drawer-title">{finding.title}</h2>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <StatusBadge status={finding.severity} />
              <StatusBadge status={finding.category} />
              {finding.disposition && <StatusBadge status={finding.disposition} />}
            </div>
          </div>
          <button className="drawer-close" onClick={onClose} aria-label="close">×</button>
        </div>
        <div className="drawer-body">
          <div className="section-label">Finding ID</div>
          <p className="section-text mono">{finding.id}</p>

          <div className="section-label">Affected asset</div>
          <p className="section-text mono">{fmt(finding.asset_id)}</p>

          <div className="section-label">Detection method</div>
          <p className="section-text">{fmt(finding.detection_method)}</p>

          {finding.supported_attack_class && (
            <>
              <div className="section-label">Supported attack class</div>
              <p className="section-text mono">{finding.supported_attack_class}</p>
            </>
          )}

          <div className="section-label">Evidence</div>
          <p className="section-text" style={{ whiteSpace: 'pre-wrap' }}>{fmt(finding.evidence)}</p>

          <div className="section-label">Confidence</div>
          <p className="section-text">
            {finding.confidence === null || finding.confidence === undefined
              ? 'Not reported'
              : `${Number(finding.confidence).toFixed(3)} (measured)`}
          </p>

          <div className="section-label">Limitations</div>
          <p className="section-text">{fmt(finding.limitations)}</p>

          <div className="section-label">Source</div>
          <dl className="kv">
            {finding.scan_id && (<><dt>Scan</dt><dd className="mono">{finding.scan_id}</dd></>)}
            {finding.created_at && (<><dt>Created</dt><dd>{finding.created_at}</dd></>)}
          </dl>

          <div className="section-label">Reviewer override</div>
          <div className="field" style={{ marginBottom: 10 }}>
            <label htmlFor="disp">Disposition</label>
            <select
              id="disp"
              className="select"
              value={disposition}
              onChange={(e) => setDisposition(e.target.value)}
            >
              {DISPOSITIONS.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>
          <div className="field" style={{ marginBottom: 10 }}>
            <label htmlFor="rnote">Reviewer note</label>
            <textarea
              id="rnote"
              className="input"
              value={reviewerNote}
              onChange={(e) => setReviewerNote(e.target.value)}
              placeholder="Why this disposition? Recorded in the audit log."
            />
          </div>
          {save.error && <div className="alert alert-error">{save.error}</div>}
          <div className="btn-row">
            <button className="btn btn-primary" onClick={handleSave} disabled={save.loading}>
              {save.loading ? 'Saving…' : 'Save review'}
            </button>
          </div>
          <p className="section-text" style={{ marginTop: 10, color: '#5d6f84', fontSize: 12 }}>
            Reviewer dispositions are recorded; they do not change measured detection results.
          </p>
        </div>
      </aside>
    </>
  );
}
