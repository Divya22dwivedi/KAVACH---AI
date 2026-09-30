import { useState } from 'react';
import type { ShiftAssessResult } from '../api/types';
import { api } from '../api/client';
import { useApi, useAsyncAction } from '../hooks/useApi';
import StatusBadge from '../components/StatusBadge';
import SvgHistogram from '../components/SvgHistogram';

const DISCLAIMER =
  'Shift assessment is statistical and indicative, not proof of compromise. The verdict is computed ' +
  'from measured distances between the two selected datasets using prototype thresholds. Confirm with ' +
  'domain review before any operational action. A verdict of NORMAL does not certify the current batch as safe.';

function toNumberArray(v: unknown): number[] | null {
  if (!Array.isArray(v)) return null;
  const nums = v.filter((x): x is number => typeof x === 'number' && Number.isFinite(x));
  return nums.length > 0 ? nums : null;
}

/** Extract histogram data from opaque shift metrics, or bin a distances array. */
function histogramFromMetrics(metrics: Record<string, unknown>): { bins: (string | number)[]; counts: number[] } | null {
  const dh = metrics['distance_histogram'];
  if (dh && typeof dh === 'object') {
    const o = dh as Record<string, unknown>;
    const bins = o['bins'];
    const counts = toNumberArray(o['counts']);
    if (Array.isArray(bins) && counts) {
      return { bins: bins.map((b) => (typeof b === 'number' || typeof b === 'string' ? b : String(b))), counts };
    }
  }
  for (const key of ['distances', 'distance_values', 'scores']) {
    const arr = toNumberArray(metrics[key]);
    if (arr) {
      const k = Math.min(20, Math.max(5, Math.floor(Math.sqrt(arr.length))));
      const min = Math.min(...arr);
      const max = Math.max(...arr);
      const width = (max - min) / k || 1;
      const counts = new Array<number>(k).fill(0);
      arr.forEach((x) => {
        const idx = Math.min(k - 1, Math.floor((x - min) / width));
        counts[idx] += 1;
      });
      const bins = Array.from({ length: k }, (_, i) => min + width * i);
      return { bins, counts };
    }
  }
  return null;
}

function fmtMetric(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') return v.toFixed(4);
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

export default function DistributionShift() {
  const datasets = useApi(api.listDatasets);
  const [refId, setRefId] = useState('');
  const [curId, setCurId] = useState('');
  const assess = useAsyncAction(api.assessShift);
  const [result, setResult] = useState<ShiftAssessResult | null>(null);

  const doAssess = async () => {
    if (!refId || !curId) return;
    const r = await assess.run(refId, curId);
    if (r) setResult(r);
  };

  const hist = result ? histogramFromMetrics(result.metrics) : null;
  const deltaEntries = result
    ? Object.entries(result.metrics).filter(([k]) => !['distance_histogram', 'distances', 'distance_values', 'scores'].includes(k))
    : [];

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Distribution Shift</h1>
        <p className="page-sub">Compare a reference dataset against a current batch; the backend returns a measured verdict and distance metrics.</p>
      </div>

      <div className="card">
        <div className="card-title">Assessment</div>
        {datasets.loading && <div className="spinner">Loading datasets…</div>}
        {datasets.error && <div className="alert alert-error">{datasets.error}</div>}
        {!datasets.loading && !datasets.error && (
          <div className="form-row">
            <div className="field">
              <label htmlFor="ref">Reference dataset</label>
              <select id="ref" className="select" value={refId} onChange={(e) => setRefId(e.target.value)}>
                <option value="">— choose —</option>
                {(datasets.data ?? []).map((d) => (
                  <option key={d.dataset_id} value={d.dataset_id}>{d.dataset_id}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="cur">Current dataset</label>
              <select id="cur" className="select" value={curId} onChange={(e) => setCurId(e.target.value)}>
                <option value="">— choose —</option>
                {(datasets.data ?? []).filter((d) => d.dataset_id !== refId).map((d) => (
                  <option key={d.dataset_id} value={d.dataset_id}>{d.dataset_id}</option>
                ))}
              </select>
            </div>
            <button className="btn btn-primary" onClick={doAssess} disabled={assess.loading || !refId || !curId}>
              {assess.loading ? 'Assessing…' : 'Assess shift'}
            </button>
          </div>
        )}
        {assess.error && <div className="alert alert-error">{assess.error}</div>}
        {!result && !assess.loading && (
          <div className="empty-state"><div className="big">Not evaluated yet</div>Select two datasets and run the assessment.</div>
        )}
      </div>

      {result && (
        <>
          <div className="card">
            <div className="card-title">Verdict (measured)</div>
            <StatusBadge status={result.verdict} />
            <div className="disclaimer">{DISCLAIMER}</div>
          </div>

          <div className="card">
            <div className="card-title">Distance histogram</div>
            {hist ? (
              <div className="chart-wrap">
                <SvgHistogram bins={hist.bins} counts={hist.counts} xLabel="distance" />
              </div>
            ) : (
              <div className="empty-state">
                <div className="big">No histogram data</div>
                The backend did not return per-sample distances or a histogram in this assessment.
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-title">Metric deltas</div>
            {deltaEntries.length === 0 ? (
              <div className="empty-state"><div className="big">No metrics</div>The backend returned no additional metrics.</div>
            ) : (
              <dl className="kv">
                {deltaEntries.map(([k, v]) => (
                  <div key={k} style={{ display: 'contents' }}>
                    <dt>{k}</dt>
                    <dd className="mono">{fmtMetric(v)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        </>
      )}
    </div>
  );
}
