import { useEffect, useRef, useState } from 'react';
import type { DatasetListItem, DatasetSample, Finding, ScanStatus } from '../api/types';
import { isEvaluated } from '../api/types';
import { api } from '../api/client';
import { useApi, useAsyncAction } from '../hooks/useApi';
import StatusBadge from '../components/StatusBadge';
import SvgBarChart from '../components/SvgBarChart';
import EvidenceDrawer from '../components/EvidenceDrawer';

function SampleThumb({ datasetId, sample, onClick }: { datasetId: string; sample: DatasetSample; onClick: () => void }) {
  const [failed, setFailed] = useState(false);
  return (
    <button className="thumb" onClick={onClick} title={sample.sample_id}>
      {failed ? (
        <div className="thumb-placeholder">image pending backend</div>
      ) : (
        <img
          src={api.sampleImageUrl(datasetId, sample.sample_id)}
          alt={`sample ${sample.sample_id}`}
          loading="lazy"
          onError={() => setFailed(true)}
        />
      )}
      <div className="thumb-meta">
        <div className="mono" style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {sample.sample_id.slice(0, 12)}
        </div>
        {sample.flags && sample.flags.length > 0 && <StatusBadge status="flag" />}
      </div>
    </button>
  );
}

const TERMINAL = ['completed', 'done', 'failed', 'error', 'success'];

export default function DataIntegrity() {
  const datasets = useApi(api.listDatasets);
  const [datasetId, setDatasetId] = useState('');
  const [uploadFormat, setUploadFormat] = useState('folder');
  const [files, setFiles] = useState<FileList | null>(null);
  const [dragging, setDragging] = useState(false);
  const upload = useAsyncAction(api.uploadDataset);
  const createScan = useAsyncAction(api.createScan);
  const [scan, setScan] = useState<ScanStatus | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);
  const [drawerFinding, setDrawerFinding] = useState<Finding | null>(null);
  const pollRef = useRef<number | null>(null);

  const samples = useApi(
    () => (datasetId ? api.getSamples(datasetId, { flagged_only: true, limit: 60 }) : Promise.resolve([] as DatasetSample[])),
    [datasetId],
  );
  const scanFindings = useApi(
    () => (scan ? api.getScanFindings(scan.scan_id) : Promise.resolve([] as Finding[])),
    [scan?.scan_id],
  );
  const evaluation = useApi(
    () => (scan ? api.getEvaluation(scan.scan_id) : Promise.resolve({ status: 'Not evaluated yet' } as const)),
    [scan?.scan_id],
  );

  useEffect(() => () => {
    if (pollRef.current) window.clearInterval(pollRef.current);
  }, []);

  const doUpload = async () => {
    if (!files || files.length === 0) return;
    const form = new FormData();
    form.append('format', uploadFormat);
    Array.from(files).forEach((f) => form.append('files', f));
    const r = await upload.run(form);
    if (r) {
      datasets.reload();
      setDatasetId(r.dataset_id);
      setScan(null);
    }
  };

  const doScan = async () => {
    if (!datasetId) return;
    setScanError(null);
    setScan(null);
    const created = await createScan.run(datasetId, {});
    if (!created) return;
    setPolling(true);
    // Poll until the scan reaches a terminal status.
    pollRef.current = window.setInterval(async () => {
      try {
        const s = await api.getScan(created.scan_id);
        setScan(s);
        if (TERMINAL.includes(s.status.trim().toLowerCase())) {
          setPolling(false);
          if (pollRef.current) window.clearInterval(pollRef.current);
        }
      } catch (e) {
        setScanError(e instanceof Error ? e.message : String(e));
        setPolling(false);
        if (pollRef.current) window.clearInterval(pollRef.current);
      }
    }, 2000);
    // Fetch once immediately too.
    try {
      const s = await api.getScan(created.scan_id);
      setScan(s);
      if (TERMINAL.includes(s.status.trim().toLowerCase())) {
        setPolling(false);
        if (pollRef.current) window.clearInterval(pollRef.current);
      }
    } catch (e) {
      setScanError(e instanceof Error ? e.message : String(e));
    }
  };

  const findingForSample = (sampleId: string): Finding | null =>
    (scanFindings.data ?? []).find((f) => {
      if (f.asset_id === sampleId) return true;
      const members = (f.evidence as Record<string, unknown> | undefined)?.members;
      return Array.isArray(members) && members.map(String).includes(sampleId);
    }) ?? null;

  const summaryItems = scan?.summary
    ? [
        { label: 'Total', value: Number(scan.summary.total ?? 0) },
        { label: 'Suspicious', value: Number(scan.summary.suspicious ?? 0) },
        { label: 'Dup groups', value: Number(scan.summary.dup_groups ?? 0) },
        { label: 'OOD', value: Number(scan.summary.ood ?? 0) },
        { label: 'Label anomalies', value: Number(scan.summary.label_anomalies ?? 0) },
      ]
    : [];

  const selectedDataset: DatasetListItem | undefined = (datasets.data ?? []).find(
    (d) => d.dataset_id === datasetId,
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Data Integrity</h1>
        <p className="page-sub">Upload or select a dataset, run an integrity scan, and inspect suspicious samples with their evidence.</p>
      </div>

      <div className="card">
        <div className="card-title">Dataset</div>
        <div className="form-row">
          <div className="field">
            <label htmlFor="ds">Select dataset</label>
            <select id="ds" className="select" value={datasetId} onChange={(e) => { setDatasetId(e.target.value); setScan(null); }}>
              <option value="">— choose —</option>
              {(datasets.data ?? []).map((d) => (
                <option key={d.dataset_id} value={d.dataset_id}>
                  {d.dataset_id} ({d.sample_count ?? '?'} samples)
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="fmt">Upload format</label>
            <select id="fmt" className="select" value={uploadFormat} onChange={(e) => setUploadFormat(e.target.value)}>
              <option value="folder">folder</option>
              <option value="csv">csv</option>
              <option value="yolo">yolo</option>
              <option value="coco">coco</option>
            </select>
          </div>
          <div className="field upload-field">
            <label htmlFor="files">Upload dataset files</label>
            <div
              className={`upload-zone${dragging ? ' is-dragging' : ''}${files?.length ? ' has-files' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => { e.preventDefault(); setDragging(false); setFiles(e.dataTransfer.files); }}
            >
              <span className="upload-icon" aria-hidden="true">↑</span>
              <span><strong>{files?.length ? `${files.length} file(s) selected` : 'Drop dataset files here'}</strong><small>or choose files · up to 50 MB</small></span>
              <input id="files" type="file" multiple aria-label="Choose dataset files" onChange={(e) => setFiles(e.target.files)} />
            </div>
          </div>
          <button className="btn btn-secondary" onClick={doUpload} disabled={upload.loading || !files || files.length === 0}>
            {upload.loading ? 'Uploading…' : 'Upload dataset'}
          </button>
        </div>
        {datasets.loading && <div className="spinner">Loading datasets…</div>}
        {datasets.error && <div className="alert alert-error">{datasets.error}</div>}
        {upload.error && <div className="alert alert-error">{upload.error}</div>}
        {upload.result && (
          <div className="alert alert-info">
            Uploaded <span className="mono">{upload.result.dataset_id}</span> — {upload.result.sample_count} samples,
            manifest <span className="mono">{upload.result.manifest_hash.slice(0, 16)}…</span>
          </div>
        )}
        {selectedDataset?.manifest_hash && (
          <dl className="kv">
            <dt>Manifest hash</dt><dd className="mono">{selectedDataset.manifest_hash}</dd>
          </dl>
        )}
      </div>

      <div className="card">
        <div className="card-title">Integrity scan</div>
        <div className="btn-row">
          <button className="btn btn-primary" onClick={doScan} disabled={createScan.loading || !datasetId}>
            {createScan.loading || polling ? 'Scanning…' : 'Run scan'}
          </button>
          {scan && (
            <span>
              Scan <span className="mono">{scan.scan_id}</span> — <StatusBadge status={scan.status} />
            </span>
          )}
        </div>
        {createScan.error && <div className="alert alert-error">{createScan.error}</div>}
        {scanError && <div className="alert alert-error">{scanError}</div>}
        {polling && <div className="spinner" style={{ marginTop: 8 }}>Scan running — polling status…</div>}
        {!scan && !createScan.loading && !polling && (
          <div className="empty-state" style={{ marginTop: 12 }}>
            <div className="big">Not evaluated yet</div>
            Select a dataset and run a scan to see integrity results.
          </div>
        )}
        {scan?.summary && (
          <div style={{ marginTop: 14 }}>
            <div className="chart-title">Scan summary counts (measured)</div>
            <div className="chart-wrap">
              <SvgBarChart items={summaryItems} />
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">Detection evaluation</div>
        {!scan && (
          <div className="empty-state"><div className="big">Not evaluated yet</div>Evaluation metrics appear after a scan completes.</div>
        )}
        {scan && evaluation.loading && <div className="spinner">Computing evaluation…</div>}
        {scan && evaluation.error && <div className="alert alert-error">{evaluation.error}</div>}
        {scan && evaluation.data && !isEvaluated(evaluation.data) && (
          <div className="empty-state"><div className="big">Not evaluated yet</div>No attack-manifest ground truth is available for this scan.</div>
        )}
        {scan && evaluation.data && isEvaluated(evaluation.data) && (
          <div>
            <p className="section-text" style={{ color: '#5d6f84' }}>
              Computed against the attack-manifest ground truth (measured, not estimated).
            </p>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Detection method</th><th>Precision</th><th>Recall</th><th>F1</th><th>FPR</th><th>Confusion (TP/FP/TN/FN)</th></tr></thead>
                <tbody>
                  {Object.entries(evaluation.data.methods).map(([m, e]) => (
                    <tr key={m}>
                      <td className="mono">{m}</td>
                      <td className="mono">{e.precision.toFixed(3)}</td>
                      <td className="mono">{e.recall.toFixed(3)}</td>
                      <td className="mono">{e.f1.toFixed(3)}</td>
                      <td className="mono">{e.fpr.toFixed(3)}</td>
                      <td className="mono">{e.confusion.tp}/{e.confusion.fp}/{e.confusion.tn}/{e.confusion.fn}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">Suspicious samples</div>
        {!datasetId && (
          <div className="empty-state"><div className="big">No dataset selected</div>Select a dataset to browse flagged samples.</div>
        )}
        {datasetId && samples.loading && <div className="spinner">Loading samples…</div>}
        {datasetId && samples.error && <div className="alert alert-error">{samples.error}</div>}
        {datasetId && !samples.loading && !samples.error && (samples.data ?? []).length === 0 && (
          <div className="empty-state"><div className="big">No flagged samples</div>Nothing flagged in this dataset so far.</div>
        )}
        {datasetId && (samples.data ?? []).length > 0 && (
          <div className="gallery">
            {(samples.data ?? []).map((s) => (
              <SampleThumb
                key={s.sample_id}
                datasetId={datasetId}
                sample={s}
                onClick={() => {
                  const f = findingForSample(s.sample_id);
                  if (f) setDrawerFinding(f);
                }}
              />
            ))}
          </div>
        )}
        <p className="section-text" style={{ marginTop: 10, color: '#5d6f84', fontSize: 12 }}>
          Click a sample to open its finding evidence (when a scan finding exists for it).
        </p>
      </div>

      <div className="card">
        <div className="card-title">Scan findings</div>
        {!scan && (
          <div className="empty-state"><div className="big">Not evaluated yet</div>No scan has been run in this session.</div>
        )}
        {scan && scanFindings.loading && <div className="spinner">Loading findings…</div>}
        {scan && scanFindings.error && <div className="alert alert-error">{scanFindings.error}</div>}
        {scan && !scanFindings.loading && !scanFindings.error && (scanFindings.data ?? []).length === 0 && (
          <div className="empty-state"><div className="big">No findings</div>The scan reported no integrity findings.</div>
        )}
        {scan && (scanFindings.data ?? []).length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Title</th><th>Severity</th><th>Confidence</th><th>Disposition</th></tr></thead>
              <tbody>
                {(scanFindings.data ?? []).map((f) => (
                  <tr key={f.id} className="clickable" onClick={() => setDrawerFinding(f)}>
                    <td>{f.title}</td>
                    <td><StatusBadge status={f.severity} /></td>
                    <td className="mono">{f.confidence === null || f.confidence === undefined ? '—' : Number(f.confidence).toFixed(3)}</td>
                    <td><StatusBadge status={f.disposition ?? 'REVIEW'} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <EvidenceDrawer
        finding={drawerFinding}
        onClose={() => setDrawerFinding(null)}
        onSaved={(u) => {
          setDrawerFinding(u);
          scanFindings.reload();
        }}
      />
    </div>
  );
}
