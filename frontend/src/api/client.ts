/**
 * Typed fetch client for the KavachAI backend (docs/api-design.md).
 * Base URL is '' so every request stays same-origin under /api
 * (Vite dev proxy forwards /api -> http://127.0.0.1:8000).
 * No runtime network calls go anywhere else.
 */
import type {
  AttackGenerateResult,
  ChainVerifyResult,
  DatasetDetail,
  DatasetListItem,
  DatasetSample,
  DatasetUploadResult,
  DemoRunResult,
  EvaluationResult,
  Finding,
  Health,
  ModelChecksResult,
  ModelInfo,
  ModelUploadResult,
  PredictResult,
  ProvenanceRecord,
  ReportGenerated,
  ScanCreated,
  ScanStatus,
  ShiftAssessResult,
  TamperDemoResult,
} from './types';

const PREFIX = '/api/v1';

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${PREFIX}${path}`, init);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === 'string' && body.detail) detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  const ct = res.headers.get('content-type') ?? '';
  if (ct.includes('application/json')) {
    return (await res.json()) as T;
  }
  return (await res.text()) as unknown as T;
}

function json<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

function query(params: Record<string, string | number | boolean | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : '';
}

export const api = {
  // Health
  health: () => request<Health>('/health'),

  // Datasets
  uploadDataset: (form: FormData) =>
    request<DatasetUploadResult>('/datasets/upload', { method: 'POST', body: form }),
  listDatasets: () => request<DatasetListItem[]>('/datasets'),
  getDataset: (id: string) => request<DatasetDetail>(`/datasets/${encodeURIComponent(id)}`),
  getSamples: (id: string, opts: { flagged_only?: boolean; limit?: number; offset?: number } = {}) =>
    request<DatasetSample[]>(
      `/datasets/${encodeURIComponent(id)}/samples${query(opts as Record<string, string | number | boolean | undefined>)}`,
    ),
  sampleImageUrl: (datasetId: string, sampleId: string) =>
    `${PREFIX}/datasets/${encodeURIComponent(datasetId)}/image/${encodeURIComponent(sampleId)}`,

  // Data-integrity scans
  createScan: (dataset_id: string, params: Record<string, unknown> = {}) =>
    json<ScanCreated>('/scans', { dataset_id, params }),
  getScan: (id: string) => request<ScanStatus>(`/scans/${encodeURIComponent(id)}`),
  getScanFindings: (id: string) =>
    request<Finding[]>(`/scans/${encodeURIComponent(id)}/findings`),

  // Models
  uploadModel: (file: File, role: 'reference' | 'candidate') => {
    const form = new FormData();
    form.append('file', file);
    form.append('role', role);
    return request<ModelUploadResult>('/models/upload', { method: 'POST', body: form });
  },
  listModels: () => request<ModelInfo[]>('/models'),
  runModelChecks: (
    id: string,
    opts: { reference_model_id?: string; probe_dataset_id: string },
  ) => json<ModelChecksResult>(`/models/${encodeURIComponent(id)}/checks`, opts),

  // Inference + provenance
  predict: (body: { model_id: string; image: string; config?: Record<string, unknown> }) =>
    json<PredictResult>('/inference/predict', body),
  getChain: (limit = 50) => request<ProvenanceRecord[]>(`/provenance/chain${query({ limit })}`),
  verifyChain: () => json<ChainVerifyResult>('/provenance/verify', {}),
  tamperDemo: (record_id: string) => json<TamperDemoResult>('/provenance/tamper-demo', { record_id }),
  anchor: () => json<{ tip_hash?: string }>('/provenance/anchor', {}),

  // Distribution shift
  assessShift: (reference_dataset_id: string, current_dataset_id: string) =>
    json<ShiftAssessResult>('/shift/assess', { reference_dataset_id, current_dataset_id }),

  // Findings
  listFindings: (filters: { category?: string; severity?: string; disposition?: string } = {}) =>
    request<Finding[]>(`/findings${query(filters)}`),
  patchFinding: (id: string, body: { disposition?: string; reviewer_note?: string }) =>
    request<Finding>(`/findings/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  // Reports (download URLs are same-origin; used as plain anchor hrefs)
  generateReport: (experiment_id: string) =>
    json<ReportGenerated>('/reports/generate', { experiment_id }),
  reportJsonUrl: (id: string) => `${PREFIX}/reports/${encodeURIComponent(id)}.json`,
  reportPdfUrl: (id: string) => `${PREFIX}/reports/${encodeURIComponent(id)}.pdf`,
  reportJson: (id: string) => request<unknown>(`/reports/${encodeURIComponent(id)}.json`),

  // Attack generator
  generateAttack: (body: { scenario: string; seed: number; n: number }) =>
    json<AttackGenerateResult>('/attacks/generate', body),

  // Evaluation
  getEvaluation: (scanId: string) =>
    request<EvaluationResult>(`/evaluation/${encodeURIComponent(scanId)}`),

  // One-click demo
  runDemo: (seed = 42) => json<DemoRunResult>('/demo/run', { seed }),
};
