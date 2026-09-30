import { useMemo, useState } from 'react';
import type { Finding } from '../api/types';
import { api } from '../api/client';
import { useApi } from '../hooks/useApi';
import FindingTable from '../components/FindingTable';
import EvidenceDrawer from '../components/EvidenceDrawer';

export default function Findings() {
  const [category, setCategory] = useState('all');
  const [severity, setSeverity] = useState('all');
  const [disposition, setDisposition] = useState('all');
  const [search, setSearch] = useState('');
  const [drawerFinding, setDrawerFinding] = useState<Finding | null>(null);

  const findingsApi = useApi(api.listFindings);

  const filtered = useMemo(() => {
    const all = findingsApi.data ?? [];
    return all.filter((f) => {
      if (category !== 'all' && f.category.trim().toLowerCase() !== category) return false;
      if (severity !== 'all' && f.severity.trim().toLowerCase() !== severity) return false;
      if (disposition !== 'all' && (f.disposition ?? 'REVIEW').trim().toUpperCase() !== disposition) return false;
      if (search.trim()) {
        const query = search.trim().toLowerCase();
        const haystack = [f.title, f.category, f.severity, f.detection_method, f.asset_id, f.id]
          .map((value) => String(value ?? '').toLowerCase());
        if (!haystack.some((value) => value.includes(query))) return false;
      }
      return true;
    });
  }, [findingsApi.data, category, severity, disposition, search]);

  const handleSaved = (updated: Finding) => {
    setDrawerFinding(updated);
    findingsApi.reload();
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Findings</h1>
        <p className="page-sub">
          All recorded findings across modules. Click a row for method, evidence, confidence and
          limitations; reviewers can record a disposition override there.
        </p>
      </div>

      <div className="card">
        {findingsApi.loading && <div className="spinner">Loading findings…</div>}
        {findingsApi.error && <div className="alert alert-error">{findingsApi.error}</div>}
        {!findingsApi.loading && !findingsApi.error && (
          <>
            <div className="form-row findings-toolbar" style={{ marginBottom: 4 }}>
              <div className="field findings-search">
                <label htmlFor="finding-search">Search findings</label>
                <input
                  id="finding-search"
                  className="input"
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Title, method, asset, or ID"
                />
              </div>
              <div className="field">
                <label htmlFor="disp">Disposition</label>
                <select id="disp" className="select" value={disposition} onChange={(e) => setDisposition(e.target.value)}>
                  <option value="all">All dispositions</option>
                  <option value="ACCEPT">ACCEPT</option>
                  <option value="REVIEW">REVIEW</option>
                  <option value="QUARANTINE">QUARANTINE</option>
                </select>
              </div>
              <div className="btn-row" style={{ marginLeft: 'auto' }}>
                <button className="btn btn-secondary btn-sm" onClick={() => findingsApi.reload()}>Refresh</button>
              </div>
            </div>
            <div className="results-count" role="status">
              Showing <strong>{filtered.length}</strong> of <strong>{findingsApi.data?.length ?? 0}</strong> findings
            </div>
            <FindingTable
              findings={filtered}
              category={category}
              severity={severity}
              onCategory={setCategory}
              onSeverity={setSeverity}
              onOpen={setDrawerFinding}
            />
          </>
        )}
      </div>

      <EvidenceDrawer finding={drawerFinding} onClose={() => setDrawerFinding(null)} onSaved={handleSaved} />
    </div>
  );
}
