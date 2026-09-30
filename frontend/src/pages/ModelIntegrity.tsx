import { useState } from 'react';
import type { ModelCheck, PredictResult } from '../api/types';
import { api } from '../api/client';
import { useApi, useAsyncAction } from '../hooks/useApi';
import StatusBadge from '../components/StatusBadge';

export default function ModelIntegrity() {
  const models = useApi(api.listModels);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [role, setRole] = useState<'reference' | 'candidate'>('reference');
  const upload = useAsyncAction(api.uploadModel);

  const [candidateId, setCandidateId] = useState('');
  const [referenceId, setReferenceId] = useState('');
  const [probeDatasetId, setProbeDatasetId] = useState('');
  const datasets = useApi(api.listDatasets);
  const checks = useAsyncAction(api.runModelChecks);
  const [checkRows, setCheckRows] = useState<ModelCheck[] | null>(null);

  // Inference probe
  const [inferModelId, setInferModelId] = useState('');
  const [inferImage, setInferImage] = useState(''); // base64 or sample_id
  const [inferResult, setInferResult] = useState<PredictResult | null>(null);
  const predict = useAsyncAction(api.predict);

  const doUpload = async () => {
    if (!file) return;
    const r = await upload.run(file, role);
    if (r) models.reload();
  };

  const doChecks = async () => {
    if (!candidateId || !probeDatasetId) return;
    const r = await checks.run(candidateId, {
      reference_model_id: referenceId || undefined,
      probe_dataset_id: probeDatasetId,
    });
    if (r) setCheckRows(r.checks);
  };

  const doPredict = async () => {
    if (!inferModelId || !inferImage) return;
    const r = await predict.run({ model_id: inferModelId, image: inferImage, config: {} });
    if (r) setInferResult(r);
  };

  const fmtOutput = (o: unknown) =>
    o === null || o === undefined ? '—' : typeof o === 'object' ? JSON.stringify(o, null, 2) : String(o);

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Model Integrity</h1>
        <p className="page-sub">Upload reference and candidate models, run integrity checks, and probe inference. All numbers shown are measured by the backend.</p>
      </div>

      <div className="card">
        <div className="card-title">Upload model</div>
        <div className="form-row">
          <div className="field upload-field">
            <label htmlFor="mfile">Upload model · .pt, .pth, .onnx, .pkl</label>
            <div
              className={`upload-zone${dragging ? ' is-dragging' : ''}${file ? ' has-files' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => { e.preventDefault(); setDragging(false); setFile(e.dataTransfer.files[0] ?? null); }}
            >
              <span className="upload-icon" aria-hidden="true">↑</span>
              <span><strong>{file?.name ?? 'Drop a model file here'}</strong><small>or choose a file · supported formats shown above</small></span>
              <input id="mfile" type="file" accept=".pt,.pth,.onnx,.pkl" aria-label="Choose model file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="mrole">Role</label>
            <select id="mrole" className="select" value={role} onChange={(e) => setRole(e.target.value as 'reference' | 'candidate')}>
              <option value="reference">reference</option>
              <option value="candidate">candidate</option>
            </select>
          </div>
          <button className="btn btn-secondary" onClick={doUpload} disabled={upload.loading || !file}>
            {upload.loading ? 'Uploading…' : 'Upload'}
          </button>
        </div>
        {upload.error && <div className="alert alert-error">{upload.error}</div>}
        {upload.result && (
          <div className="alert alert-info">
            <dl className="kv">
              <dt>Model ID</dt><dd className="mono">{upload.result.model_id}</dd>
              <dt>SHA-256</dt><dd className="mono">{upload.result.sha256}</dd>
              <dt>Format</dt><dd>{upload.result.format}</dd>
              {upload.result.metadata && (
                <><dt>Metadata</dt><dd className="mono" style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(upload.result.metadata, null, 2)}</dd></>
              )}
            </dl>
          </div>
        )}
        <p className="section-text" style={{ color: '#5d6f84', fontSize: 12 }}>
          .pt/.pth files are hashed with a safe zip listing only; .pkl executes only if its digest matches a KavachAI manifest.
        </p>
      </div>

      <div className="card">
        <div className="card-title">Run integrity checks</div>
        {models.loading && <div className="spinner">Loading models…</div>}
        {models.error && <div className="alert alert-error">{models.error}</div>}
        {!models.loading && !models.error && (
          <>
            <div className="form-row">
              <div className="field">
                <label htmlFor="cand">Candidate model</label>
                <select id="cand" className="select" value={candidateId} onChange={(e) => setCandidateId(e.target.value)}>
                  <option value="">— choose —</option>
                  {(models.data ?? []).map((m) => (
                    <option key={m.model_id} value={m.model_id}>{m.model_id} ({m.role ?? m.format ?? '?'})</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="ref">Reference model (optional)</label>
                <select id="ref" className="select" value={referenceId} onChange={(e) => setReferenceId(e.target.value)}>
                  <option value="">— none —</option>
                  {(models.data ?? []).filter((m) => m.model_id !== candidateId).map((m) => (
                    <option key={m.model_id} value={m.model_id}>{m.model_id}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="probe">Probe dataset</label>
                <select id="probe" className="select" value={probeDatasetId} onChange={(e) => setProbeDatasetId(e.target.value)}>
                  <option value="">— choose —</option>
                  {(datasets.data ?? []).map((d) => (
                    <option key={d.dataset_id} value={d.dataset_id}>{d.dataset_id}</option>
                  ))}
                </select>
              </div>
              <button className="btn btn-primary" onClick={doChecks} disabled={checks.loading || !candidateId || !probeDatasetId}>
                {checks.loading ? 'Running checks…' : 'Run checks'}
              </button>
            </div>
            {checks.error && <div className="alert alert-error">{checks.error}</div>}
            {!checkRows && !checks.loading && (
              <div className="empty-state"><div className="big">Not evaluated yet</div>Run checks to see measured results for hash verification, metadata, behaviour comparison, trigger test, and weight statistics.</div>
            )}
            {checkRows && (
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>Check</th><th>Status</th><th>Measured result / note</th></tr></thead>
                  <tbody>
                    {checkRows.map((c, i) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 600 }}>{c.check_name}</td>
                        <td><StatusBadge status={c.status} /></td>
                        <td style={{ whiteSpace: 'pre-wrap' }}>{c.result ? `${JSON.stringify(c.result)} — ` : ''}{c.note || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      <div className="card">
        <div className="card-title">Inference probe (appends a provenance record)</div>
        <div className="form-row">
          <div className="field">
            <label htmlFor="imodel">Model</label>
            <select id="imodel" className="select" value={inferModelId} onChange={(e) => setInferModelId(e.target.value)}>
              <option value="">— choose —</option>
              {(models.data ?? []).map((m) => (
                <option key={m.model_id} value={m.model_id}>{m.model_id}</option>
              ))}
            </select>
          </div>
          <div className="field" style={{ flex: 1, minWidth: 260 }}>
            <label htmlFor="iimg">Image (base64 data or sample_id)</label>
            <input
              id="iimg"
              className="input"
              value={inferImage}
              onChange={(e) => setInferImage(e.target.value)}
              placeholder="sample_000123 or data:image/png;base64,…"
            />
          </div>
          <button className="btn btn-secondary" onClick={doPredict} disabled={predict.loading || !inferModelId || !inferImage}>
            {predict.loading ? 'Predicting…' : 'Predict'}
          </button>
        </div>
        {predict.error && <div className="alert alert-error">{predict.error}</div>}
        {!inferResult && !predict.loading && (
          <div className="empty-state"><div className="big">No inference run yet</div>Predictions append tamper-evident records to the provenance ledger.</div>
        )}
        {inferResult && (
          <dl className="kv">
            <dt>Record</dt><dd className="mono">{inferResult.record_id}</dd>
            <dt>Record hash</dt><dd className="mono">{inferResult.record_hash}</dd>
            <dt>Output</dt><dd className="mono" style={{ whiteSpace: 'pre-wrap' }}>{fmtOutput(inferResult.output)}</dd>
          </dl>
        )}
      </div>
    </div>
  );
}
