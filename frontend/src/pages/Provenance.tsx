import { useState } from 'react';
import { api } from '../api/client';
import { useApi, useAsyncAction } from '../hooks/useApi';
import StatusBadge from '../components/StatusBadge';
import ChainVisualizer from '../components/ChainVisualizer';

export default function Provenance() {
  const chain = useApi(() => api.getChain(60));
  const verify = useAsyncAction(api.verifyChain);
  const tamper = useAsyncAction(api.tamperDemo);
  const anchor = useAsyncAction(api.anchor);
  const [verifyResult, setVerifyResult] = useState<import('../api/types').ChainVerifyResult | null>(null);
  const [tamperResult, setTamperResult] = useState<import('../api/types').TamperDemoResult | null>(null);
  const [tamperRecordId, setTamperRecordId] = useState('');

  const records = chain.data ?? [];

  const doVerify = async () => {
    const r = await verify.run();
    if (r) setVerifyResult(r);
  };

  const doTamper = async () => {
    if (!tamperRecordId) return;
    const r = await tamper.run(tamperRecordId);
    if (r) {
      setTamperResult(r);
      chain.reload();
    }
  };

  const doAnchor = async () => {
    const r = await anchor.run();
    if (r) chain.reload();
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Provenance Ledger</h1>
        <p className="page-sub">
          Tamper-evident cryptographic provenance ledger (SHA-256 hash chain). Every inference
          prediction appends a record linking to the previous hash.
        </p>
      </div>

      <div className="card">
        <div className="card-title">Chain</div>
        <div className="btn-row" style={{ marginBottom: 14 }}>
          <button className="btn btn-primary" onClick={doVerify} disabled={verify.loading}>
            {verify.loading ? 'Verifying…' : 'Verify chain'}
          </button>
          <button className="btn btn-secondary" onClick={doAnchor} disabled={anchor.loading}>
            {anchor.loading ? 'Anchoring…' : 'Anchor tip hash'}
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => chain.reload()}>Refresh</button>
        </div>
        {chain.loading && <div className="spinner">Loading chain…</div>}
        {chain.error && <div className="alert alert-error">{chain.error}</div>}
        {verify.error && <div className="alert alert-error">{verify.error}</div>}
        {anchor.error && <div className="alert alert-error">{anchor.error}</div>}
        {anchor.result && anchor.result.tip_hash && (
          <div className="alert alert-info">Anchored tip hash <span className="mono">{anchor.result.tip_hash}</span> (local anchor record; external anchoring is future work).</div>
        )}
        {!chain.loading && !chain.error && (
          <ChainVisualizer records={records} brokenAt={verifyResult?.broken_at ?? null} />
        )}

        {!verifyResult && !verify.loading && (
          <div className="empty-state" style={{ marginTop: 12 }}>
            <div className="big">Not evaluated yet</div>
            Press “Verify chain” to check ledger integrity.
          </div>
        )}
        {verifyResult && (
          <div className="alert" style={{ marginTop: 12, background: verifyResult.intact ? '#e2f2e8' : '#f9e4e2', borderColor: verifyResult.intact ? '#bfe0c9' : '#f0c4c0' }}>
            <StatusBadge status={verifyResult.intact ? 'intact' : 'broken'} />{' '}
            {verifyResult.intact ? (
              <span>Chain intact — every record hash links correctly.</span>
            ) : (
              <span>
                Chain broken at <span className="mono">RECORD {verifyResult.broken_at}</span>
                {verifyResult.expected_hash && (
                  <span> — expected <span className="mono">{verifyResult.expected_hash.slice(0, 16)}…</span>, got <span className="mono">{verifyResult.actual_hash?.slice(0, 16)}…</span></span>
                )}
              </span>
            )}
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">Synthetic tamper demonstration</div>
        <p className="section-text" style={{ color: '#5d6f84' }}>
          Modifies the output of a <strong>sandboxed copy</strong> of a record and shows before/after.
          This is a labeled synthetic demonstration for evaluating detection — not an attack on real data.
        </p>
        <div className="form-row">
          <div className="field">
            <label htmlFor="trec">Record</label>
            <select id="trec" className="select" value={tamperRecordId} onChange={(e) => setTamperRecordId(e.target.value)}>
              <option value="">— choose —</option>
              {records.map((r) => (
                <option key={r.record_id} value={r.record_id}>{r.record_id}</option>
              ))}
            </select>
          </div>
          <button className="btn btn-danger" onClick={doTamper} disabled={tamper.loading || !tamperRecordId}>
            {tamper.loading ? 'Tampering…' : 'Run synthetic tamper demo'}
          </button>
        </div>
        {tamper.error && <div className="alert alert-error">{tamper.error}</div>}
        {tamperResult && (
          <div>
            <div className="alert alert-warn">
              Synthetic tamper demonstration — sandboxed copy of <span className="mono">RECORD {tamperResult.record_id}</span>.
            </div>
            <dl className="kv">
              <dt>Before (output hash)</dt><dd className="mono" style={{ whiteSpace: 'pre-wrap' }}>{tamperResult.before_output_hash}</dd>
              <dt>After (output hash)</dt><dd className="mono" style={{ whiteSpace: 'pre-wrap' }}>{tamperResult.after_output_hash}</dd>
              <dt>Note</dt><dd>{tamperResult.note}</dd>
            </dl>
            <div className="btn-row" style={{ marginTop: 10 }}>
              <button className="btn btn-secondary" onClick={doVerify}>Re-verify chain</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
