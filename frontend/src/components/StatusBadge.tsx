/** Restrained status pill. Never invents a verdict — maps backend statuses to color only. */
const MAP: Record<string, string> = {
  // positive
  ok: 'b-green', pass: 'b-green', intact: 'b-green', normal: 'b-green',
  // caution / review
  review: 'b-amber', flag: 'b-amber', expected_drift: 'b-amber', running: 'b-amber',
  pending: 'b-amber', queued: 'b-amber', acknowledged: 'b-amber',
  // negative
  quarantine: 'b-red', broken: 'b-red', suspicious_shift: 'b-red', failed: 'b-red',
  error: 'b-red', critical: 'b-red', high: 'b-red',
  // informational
  info: 'b-blue', low: 'b-blue', open: 'b-blue',
  // disposition: ACCEPT reads as positive
  accept: 'b-green',
  // unevaluated / unknown
  'not evaluated yet': 'b-gray', unknown: 'b-gray', unavailable: 'b-gray', resolved: 'b-gray',
  false_positive: 'b-gray', medium: 'b-gray',
};

export default function StatusBadge({ status }: { status: string }) {
  const key = status.trim().toLowerCase();
  const cls = MAP[key] ?? 'b-gray';
  return <span className={`badge ${cls}`}>{status}</span>;
}
