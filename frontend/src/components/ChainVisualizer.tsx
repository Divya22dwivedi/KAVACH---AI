import type { ProvenanceRecord } from '../api/types';

function short(h: string): string {
  if (!h) return '—';
  return h.length > 18 ? `${h.slice(0, 10)}…${h.slice(-6)}` : h;
}

interface Props {
  records: ProvenanceRecord[];
  brokenAt?: string | null;
}

/**
 * Tamper-evident cryptographic provenance ledger visualizer.
 * RECORD boxes: green = hash matches, red = hash mismatch.
 * Never described as a blockchain.
 */
export default function ChainVisualizer({ records, brokenAt }: Props) {
  if (records.length === 0) {
    return <div className="empty-state"><div className="big">No provenance records</div>No inference records have been appended yet.</div>;
  }
  return (
    <div className="chain" aria-label="provenance chain">
      {records.map((r, i) => {
        const broken = brokenAt != null && r.record_id === brokenAt;
        return (
          <span key={r.record_id} style={{ display: 'flex', alignItems: 'stretch' }}>
            <span className={`chain-node ${broken ? 'broken' : 'ok'}`}>
              <div className="rec-id">RECORD {r.record_id}</div>
              <div className="hash" title={`prev: ${r.prev_hash}\ncurrent: ${r.record_hash}`}>
                prev&nbsp;&nbsp;{short(r.prev_hash)}
                <br />
                cur&nbsp;&nbsp;&nbsp;{short(r.record_hash)}
              </div>
              {broken && <div className="hash" style={{ color: '#b3261e', fontWeight: 700 }}>hash mismatch</div>}
            </span>
            {i < records.length - 1 && <span className="chain-arrow">→</span>}
          </span>
        );
      })}
    </div>
  );
}
