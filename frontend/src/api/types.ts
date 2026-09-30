/**
 * KavachAI frontend type definitions.
 * Aligned with the backend (Phase 10 integration contract):
 *  - Finding: { id, scan_id, category, asset_id, title, detection_method,
 *    evidence (object), confidence, severity, disposition, supported_attack_class,
 *    limitations, reviewer_note, created_at }
 *  - disposition vocabulary: 'ACCEPT' | 'REVIEW' | 'QUARANTINE'
 *    (system recommendation; the reviewer may override via PATCH)
 *  - Severity: critical | high | medium | low | info
 *  - ModelCheck: { check_name, status, result, note }
 *  - Provenance record: { seq, record_id, input_hash, model_hash, config_hash,
 *    model_version, output_json, output_hash, created_at, prev_hash, record_hash }
 *  - Shift metrics carry distance_histogram { bins, counts } when available.
 */

export interface Health {
  status: string;
  version: string;
  db_ok: boolean;
  offline: boolean;
}

export interface DatasetUploadResult {
  dataset_id: string;
  sample_count: number;
  manifest_hash: string;
}

export interface DatasetListItem {
  dataset_id: string;
  sample_count?: number;
  manifest_hash?: string;
  name?: string;
  created_at?: string;
}

export interface DatasetDetail extends DatasetListItem {
  sample_count: number;
}

export interface DatasetSample {
  sample_id: string;
  label?: string;
  flags?: string[];
  finding_id?: string;
  [key: string]: unknown;
}

export interface ScanSummary {
  total?: number;
  suspicious?: number;
  dup_groups?: number;
  ood?: number;
  label_anomalies?: number;
  [key: string]: unknown;
}

export interface ScanStatus {
  scan_id: string;
  status: string;
  summary?: ScanSummary;
  experiment_id?: string;
}

export interface ScanCreated {
  scan_id: string;
  experiment_id: string;
}

export type FindingCategory = 'data' | 'model' | 'provenance' | 'shift';
export type Disposition = 'ACCEPT' | 'REVIEW' | 'QUARANTINE';

export interface Finding {
  id: string;
  category: string;
  severity: string;
  title: string;
  asset_id?: string;
  detection_method?: string;
  evidence?: Record<string, unknown>;
  confidence?: number | null;
  supported_attack_class?: string | null;
  limitations?: string;
  disposition?: Disposition | string | null;
  reviewer_note?: string | null;
  scan_id?: string;
  created_at?: string;
}

export interface ModelInfo {
  model_id: string;
  sha256?: string;
  format?: string;
  metadata?: Record<string, unknown>;
  role?: string;
}

export interface ModelUploadResult {
  model_id: string;
  sha256: string;
  format: string;
  metadata?: Record<string, unknown>;
}

export type ModelCheckStatus = 'pass' | 'flag' | 'unavailable';

export interface ModelCheck {
  check_name: string;
  status: ModelCheckStatus;
  result?: Record<string, unknown>;
  note: string;
}

export interface ModelChecksResult {
  checks: ModelCheck[];
}

export interface PredictResult {
  record_id: string;
  output: unknown;
  record_hash: string;
}

export interface ProvenanceRecord {
  seq?: number;
  record_id: string;
  input_hash?: string;
  model_hash?: string;
  config_hash?: string;
  output_hash?: string;
  prev_hash: string;
  record_hash: string;
  created_at?: string;
}

export interface ChainVerifyResult {
  intact: boolean;
  broken_at: string | null;
  expected_hash?: string;
  actual_hash?: string;
}

export interface TamperDemoResult {
  record_id: string;
  before_output_hash: string;
  after_output_hash: string;
  note: string;
}

export type ShiftVerdict = 'NORMAL' | 'EXPECTED_DRIFT' | 'SUSPICIOUS_SHIFT';

export interface ShiftAssessResult {
  verdict: ShiftVerdict;
  metrics: Record<string, unknown>;
}

export interface ReportGenerated {
  report_id: string;
}

export interface AttackGenerateResult {
  dataset_id: string;
  attack_id: string;
  manifest: unknown;
}

export interface MethodEvaluation {
  precision: number;
  recall: number;
  f1: number;
  fpr: number;
  confusion: { tp: number; fp: number; tn: number; fn: number };
}

export interface Evaluated {
  status: 'evaluated';
  methods: Record<string, MethodEvaluation>;
}

export interface NotEvaluated {
  status: 'Not evaluated yet';
}

export type EvaluationResult = Evaluated | NotEvaluated;

export function isEvaluated(r: EvaluationResult): r is Evaluated {
  return (r as Evaluated).status === 'evaluated';
}

export interface DemoStep {
  name: string;
  ok: boolean;
  ms: number;
  detail?: unknown;
}

export interface DemoRunResult {
  experiment_id: string;
  steps: DemoStep[];
  report_id: string;
  pdf_url?: string;
}
