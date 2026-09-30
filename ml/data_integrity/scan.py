"""Module 1 — Data integrity scan.

Implements docs/ml-methodology.md "Module 1 — Data integrity" exactly:

  1. exact duplicates: group by sha256 (info if same label+contributor,
     medium on label/contributor conflict)
  2. near-duplicates: dHash graph, edge = Hamming <= 6; connected component
     size >= 3 -> "flooding candidate" (medium, REVIEW)
  3. representation outlier (Spectral-Signatures-inspired, bounded):
     per class PCA(16) -> reconstruction error; flag samples above the
     ``outlier_percentile`` (default 99) of the class error distribution.
     Confidence = min(0.95, sample_percentile/100)
  4. label-distribution anomaly: chi-square of observed class counts vs the
     declared distribution (default uniform); p < 0.01 -> dataset-level
     finding; per-class |z| > 3 -> class-level finding
  5. activation-clustering-inspired (bounded): per-class KMeans(k=2) on PCA
     features; minority cluster <= 15% of class AND centroid distance > 2
     sigma -> flag members (confidence 0.55, REVIEW)
  6. trigger-patch heuristic (bounded): for flagged outliers, patch-energy
     map |image - class median|; compact high-energy region (< 5% of pixels,
     energy > 5x median) -> "trigger-like patch" *evidence attached* to the
     outlier finding (never a standalone verdict)
  7. contributor aggregation: per contributor anomaly rate vs global rate
     (binomial test, p < 0.05, >= 5 samples) -> contributor-level finding

Confidence rules: methods 3 and 5 use the methodology's definitions. For the
remaining methods the methodology gives no per-finding confidence, so this
prototype documents fixed rules here (never invented per finding):
  - exact duplicate:  0.95 (deterministic sha256 equality)
  - near-duplicate:   0.70 (dHash <= 6 is a documented heuristic)
  - chi-square:       min(0.95, 1 - p)
  - class z-score:    0.60
  - contributor:      min(0.90, 1 - p)

Severity/disposition follow the methodology's severity ladder and the
Module 5 disposition policy (critical/high -> QUARANTINE; medium/low ->
REVIEW; info -> ACCEPT). Language: "Suspicious" / "Anomalous" / "Requires
review". Malicious intent is never asserted.

``run_scan(dataset, scan_id, params=None, seed=7)`` returns
``(findings, summary)``. ``dataset`` is a row list (as produced by
``ingest``) or a path (auto-detected layout). All thresholds live in
``params`` (defaults below) and are echoed in the summary, per the
methodology's "stored per-run in params_json" rule.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

from ml.common.features import extract_features
from ml.common.hashing import dhash, hamming_hex, sha256_file
from ml.common.utils import utcnow

from .ingest import IngestError, load_dataset

GRAY_SIZE = 32  # working resolution for the patch-energy heuristic

DEFAULT_PARAMS = {
    "dhash_hamming_threshold": 6,
    "min_flood_component_size": 3,   # >=3 -> "flooding candidate"
    "pca_components": 16,
    "outlier_percentile": 99,        # methodology default
    "chisquare_p": 0.01,
    "class_zscore": 3.0,
    "kmeans_minority_frac": 0.15,
    "kmeans_centroid_sigma": 2.0,
    "patch_energy_ratio": 5.0,
    "patch_max_fraction": 0.05,
    "contrib_p": 0.05,
    "contrib_min_samples": 5,
}


# ---------------------------------------------------------------------------
# helpers


def _j(o):
    """Make evidence JSON-safe (no numpy scalars)."""
    if isinstance(o, dict):
        return {k: _j(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_j(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return _j(o.tolist())
    return o


def _union_find_components(n: int, edges: list[tuple[int, int]]
                           ) -> list[list[int]]:
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    comps: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        comps[find(i)].append(i)
    return [sorted(v) for v in comps.values() if len(v) >= 2]


def _patch_evidence(gray: np.ndarray, class_median: np.ndarray,
                    energy_ratio: float, max_frac: float) -> dict | None:
    """Trigger-patch energy heuristic: compact high-energy region vs median.

    A trigger patch is a *compact* region near the global energy maximum.
    This matters because poisoned samples are often relabeled to the target
    class, so their whole-image content differs diffusely from the class
    median; a plain pixel-fraction gate then rejects them. Here we take
    pixels near the energy maximum and require their bounding box to be
    compact (< max_frac of the image). Threshold = max(0.8 * global max,
    energy_ratio * median pixel difference).

    Returns an evidence dict or None. Heuristic only — never a verdict.
    """
    diff = np.abs(gray.astype(np.float64) - class_median.astype(np.float64))
    mx = float(diff.max())
    if mx <= 0:
        return None
    med = float(np.median(diff))
    thr = max(0.8 * mx, energy_ratio * med)
    ys, xs = np.nonzero(diff > thr)
    if len(ys) < 4:
        return None
    bbox_frac = float(((ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1))
                      / diff.size)
    if bbox_frac >= max_frac:
        return None
    return {
        "trigger_like_patch": True,
        "bbox_xyxy": [int(xs.min()), int(ys.min()),
                      int(xs.max()), int(ys.max())],
        "patch_pixel_fraction": float(len(ys) / diff.size),
        "bbox_fraction": bbox_frac,
        "energy_threshold": thr,
        "energy_ratio_threshold": energy_ratio,
        "median_energy": med,
        "note": ("compact high-energy region vs class median "
                 "(heuristic evidence only, not a verdict)"),
    }


# ---------------------------------------------------------------------------
# main entry point


def run_scan(dataset, scan_id: str, params: dict | None = None,
             seed: int = 7) -> tuple[list[dict], dict]:
    """Run the Module 1 data-integrity scan.

    Returns (findings, summary). Every number in findings/summary is measured
    from the scanned data; nothing is invented.
    """
    p = dict(DEFAULT_PARAMS)
    if params:
        p.update(params)
    seed = int(seed)

    if isinstance(dataset, (str, Path)):
        rows, meta = load_dataset(dataset)
        declared = (meta.get("manifest") or {}).get("class_distribution")
    else:
        rows, declared = list(dataset), None
    if not rows:
        raise IngestError("run_scan: empty dataset")

    sids = [r["sample_id"] for r in rows]
    if len(set(sids)) != len(sids):
        raise IngestError("run_scan: duplicate sample_id values")
    for r in rows:
        if not Path(r["abs_path"]).is_file():
            raise IngestError(
                f"run_scan: missing image file for {r['sample_id']}")

    n = len(rows)
    # -- per-image artifacts (measured once) -------------------------------
    sha = [sha256_file(Path(r["abs_path"])) for r in rows]
    dh, dh_int, feats, gray32 = [], [], [], []
    for r in rows:
        img = Image.open(r["abs_path"]).convert("RGB")
        h = dhash(img)
        dh.append(h)
        dh_int.append(int(h, 16))
        feats.append(extract_features(img))
        gray32.append(np.asarray(img.convert("L").resize(
            (GRAY_SIZE, GRAY_SIZE), Image.LANCZOS), dtype=np.uint8))
    feats = np.stack(feats)
    gray32 = np.stack(gray32)

    findings: list[dict] = []
    fid = 0

    def add(*, asset_id, title, detection_method, evidence, confidence,
            severity, disposition, supported_attack_class, limitations):
        nonlocal fid
        fid += 1
        findings.append({
            "id": f"F-{fid:04d}",
            "scan_id": scan_id,
            "category": "data",
            "asset_id": asset_id,
            "title": title,
            "detection_method": detection_method,
            "evidence": _j(evidence),
            "confidence": float(confidence),
            "severity": severity,
            "disposition": disposition,
            "supported_attack_class": supported_attack_class,
            "limitations": limitations,
            "created_at": utcnow(),
        })

    flagged_samples: set[str] = set()   # any sample-level finding
    rep_anomaly_samples: set[str] = set()  # methods 3/5 (OOD candidates)
    methods_run: list[str] = []
    n_exact_groups = 0
    n_near_components = 0
    n_label_anomalies = 0
    n_contrib_flags = 0

    # -- 1. exact duplicates ------------------------------------------------
    methods_run.append("exact_sha256")
    by_hash: dict[str, list[int]] = defaultdict(list)
    for i, h in enumerate(sha):
        by_hash[h].append(i)
    for h in sorted(by_hash):
        idxs = by_hash[h]
        if len(idxs) < 2:
            continue
        n_exact_groups += 1
        labels = {rows[i].get("label") for i in idxs}
        contribs = {rows[i].get("contributor_id") for i in idxs}
        conflict = len(labels) > 1 or len(contribs) > 1
        members = [sids[i] for i in idxs]
        flagged_samples.update(members)
        if conflict:
            title = ("Suspicious: exact-duplicate image files with "
                     "conflicting labels/contributors — requires review")
            severity, disposition = "medium", "REVIEW"
        else:
            title = ("Exact-duplicate image files "
                     "(same label and contributor)")
            severity, disposition = "info", "ACCEPT"
        add(asset_id=f"dup-exact-{n_exact_groups:02d}", title=title,
            detection_method="exact_sha256",
            evidence={"sha256": h, "group_size": len(idxs),
                      "members": members,
                      "labels": sorted(str(x) for x in labels),
                      "contributors": sorted(str(x) for x in contribs),
                      "label_or_contributor_conflict": conflict},
            confidence=0.95, severity=severity, disposition=disposition,
            supported_attack_class="data_poisoning.duplicate_injection",
            limitations=("SHA-256 equality is deterministic, but duplicates "
                         "may be benign (e.g. intentional oversampling); "
                         "only the label/contributor conflict is suspicious."))

    # -- 2. near-duplicate graph -------------------------------------------
    methods_run.append("dhash_graph")
    thr = int(p["dhash_hamming_threshold"])
    edges = [(a, b) for a in range(n) for b in range(a + 1, n)
             if bin(dh_int[a] ^ dh_int[b]).count("1") <= thr]
    for comp in _union_find_components(n, edges):
        n_near_components += 1
        members = [sids[i] for i in comp]
        flagged_samples.update(members)
        flood = len(comp) >= int(p["min_flood_component_size"])
        if flood:
            title = (f"Suspicious: near-duplicate flooding candidate "
                     f"({len(comp)} near-identical images) — requires review")
            severity = "medium"
        else:
            title = (f"Near-duplicate image pair/group "
                     f"({len(comp)} images) — requires review")
            severity = "low"
        add(asset_id=f"dup-near-{n_near_components:02d}", title=title,
            detection_method="dhash_graph",
            evidence={"group_size": len(comp), "members": members,
                      "dhash_hex": [dh[i] for i in comp],
                      "hamming_threshold": thr,
                      "flooding_candidate": flood},
            confidence=0.70, severity=severity, disposition="REVIEW",
            supported_attack_class="data_poisoning.duplicate_injection",
            limitations=("dHash Hamming <= 6 is a heuristic tuned on the "
                         "KavachAI synthetic generator; near-duplicates may "
                         "be benign (augmentation, bursts). Component size "
                         ">= 3 is treated as a flooding *candidate*, not "
                         "proof of intent."))

    # -- per-class index ----------------------------------------------------
    by_class: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        if r.get("label") is not None:
            by_class[str(r["label"])].append(i)

    k = int(p["pca_components"])
    pct = float(p["outlier_percentile"])
    class_pca: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    # (Z, err, idxs) per class with enough samples

    # -- 3. representation outliers (+ 6. patch evidence) -------------------
    methods_run.append("pca_reconstruction_outlier")
    for label in sorted(by_class):
        idxs = by_class[label]
        if len(idxs) < k + 1:
            continue  # too few samples for a k-dim PCA; skip silently
        X = feats[idxs]
        model = PCA(n_components=k, random_state=seed)
        Z = model.fit_transform(X)
        err = ((X - model.inverse_transform(Z)) ** 2).sum(axis=1)
        class_pca[label] = (Z, err, np.array(idxs))
        cutoff = float(np.percentile(err, pct))
        median_gray = np.median(gray32[idxs], axis=0).astype(np.uint8)
        for j, e in enumerate(err):
            if not e > cutoff:
                continue
            sid = sids[idxs[j]]
            flagged_samples.add(sid)
            rep_anomaly_samples.add(sid)
            sample_pct = float(stats.percentileofscore(err, e, kind="strict"))
            evidence = {
                "class": label,
                "class_size": len(idxs),
                "reconstruction_error": float(e),
                "percentile_cutoff": pct,
                "cutoff_value": cutoff,
                "sample_percentile": sample_pct,
                "pca_components": k,
            }
            attack_cls = None
            patch = _patch_evidence(gray32[idxs[j]], median_gray,
                                    float(p["patch_energy_ratio"]),
                                    float(p["patch_max_fraction"]))
            if patch:
                evidence["trigger_patch_heuristic"] = patch
                attack_cls = "backdoor.trigger_patch"
            add(asset_id=sid,
                title=("Suspicious representation outlier (requires review): "
                       f"sample {sid} in class '{label}'"),
                detection_method="pca_reconstruction_outlier",
                evidence=evidence,
                confidence=min(0.95, sample_pct / 100.0),
                severity="medium", disposition="REVIEW",
                supported_attack_class=attack_cls,
                limitations=("Spectral-Signatures-inspired bounded baseline "
                             "on handcrafted features + PCA (weaker than "
                             "learned deep representations); high "
                             "reconstruction error can also come from rare "
                             "but benign samples, mislabels, or OOD data. "
                             "Weak against adaptive triggers."))

    # -- 4. label-distribution anomaly --------------------------------------
    methods_run.append("label_chisquare")
    labeled = [(i, str(rows[i]["label"])) for i in range(n)
               if rows[i].get("label") is not None]
    if labeled:
        classes = sorted({c for _, c in labeled})
        obs = np.array([sum(1 for _, c in labeled if c == cl)
                        for cl in classes], dtype=float)
        total_labeled = float(obs.sum())
        if isinstance(declared, dict) and set(classes) <= set(declared):
            probs = np.array([declared[cl] for cl in classes], dtype=float)
            probs = probs / probs.sum()
        else:
            probs = np.full(len(classes), 1.0 / len(classes))  # uniform
        exp = probs * total_labeled
        chi2, pval = stats.chisquare(obs, exp)
        if pval < float(p["chisquare_p"]):
            n_label_anomalies += 1
            sev = "medium" if pval < 0.001 else "low"
            add(asset_id="dataset",
                title=("Anomalous label distribution (requires review): "
                       "class counts deviate from the declared distribution"),
                detection_method="label_chisquare",
                evidence={"observed": {c: int(o)
                                       for c, o in zip(classes, obs)},
                          "expected": {c: float(e)
                                       for c, e in zip(classes, exp)},
                          "declared_distribution":
                              "uniform" if declared is None else "manifest",
                          "chi2_statistic": float(chi2),
                          "p_value": float(pval),
                          "p_threshold": float(p["chisquare_p"])},
                confidence=min(0.95, 1.0 - float(pval)),
                severity=sev, disposition="REVIEW",
                supported_attack_class="data_poisoning.label_flip",
                limitations=("A skewed class distribution is anomalous "
                             "relative to the declared distribution, not "
                             "proof of label tampering; natural imbalance "
                             "is a common benign cause."))
        z_thr = float(p["class_zscore"])
        for cl, o, e in zip(classes, obs, exp):
            z = float((o - e) / np.sqrt(e)) if e > 0 else 0.0
            if abs(z) > z_thr:
                n_label_anomalies += 1
                add(asset_id=f"class:{cl}",
                    title=(f"Anomalous class count for '{cl}' (requires "
                           f"review): z={z:.2f}"),
                    detection_method="label_zscore",
                    evidence={"class": cl, "observed": int(o),
                              "expected": float(e), "z_score": z,
                              "z_threshold": z_thr},
                    confidence=0.60, severity="low", disposition="REVIEW",
                    supported_attack_class="data_poisoning.label_flip",
                    limitations=("Class-level count anomaly only; may be "
                                 "benign imbalance."))

    # -- 5. activation-clustering-inspired minority cluster ------------------
    methods_run.append("kmeans_minority_cluster")
    min_frac = float(p["kmeans_minority_frac"])
    sig_thr = float(p["kmeans_centroid_sigma"])
    for label in sorted(class_pca):
        Z, _, idxs_arr = class_pca[label]
        m = len(idxs_arr)
        if m < 10:
            continue
        km = KMeans(n_clusters=2, n_init=10, random_state=seed).fit(Z)
        lab = km.labels_
        sizes = np.bincount(lab, minlength=2)
        minority = int(np.argmin(sizes))
        frac = float(sizes[minority] / m)
        if frac > min_frac or sizes[minority] == 0:
            continue
        c0, c1 = km.cluster_centers_
        axis = c1 - c0
        norm = float(np.linalg.norm(axis))
        if norm <= 0:
            continue
        unit = axis / norm
        proj = Z @ unit
        sigma = float(proj.std())
        if sigma <= 0:
            continue
        dist_sigma = float(abs((c0 - c1) @ unit) / sigma)
        if dist_sigma <= sig_thr:
            continue
        members = [sids[int(i)] for i in idxs_arr[lab == minority]]
        flagged_samples.update(members)
        rep_anomaly_samples.update(members)
        add(asset_id=f"cluster:{label}:{minority}",
            title=(f"Suspicious minority cluster in class '{label}' "
                   f"(requires review): {len(members)}/{m} samples"),
            detection_method="kmeans_minority_cluster",
            evidence={"class": label, "class_size": m,
                      "cluster": minority,
                      "minority_size": len(members),
                      "minority_fraction": frac,
                      "minority_fraction_threshold": min_frac,
                      "centroid_distance_sigma": dist_sigma,
                      "centroid_sigma_threshold": sig_thr,
                      "members": members},
            confidence=0.55, severity="low", disposition="REVIEW",
            supported_attack_class=None,
            limitations=("Activation-Clustering-inspired bounded baseline "
                         "on handcrafted PCA features (not learned "
                         "activations). Needs enough anomalous samples to "
                         "form a cluster; ineffective at very low anomaly "
                         "rates. A tight minority cluster may be a benign "
                         "sub-population."))

    # -- 7. contributor aggregation ------------------------------------------
    methods_run.append("contributor_binomial")
    p0 = len(flagged_samples) / n if n else 0.0
    if p0 > 0:
        by_contrib: dict[str, list[int]] = defaultdict(list)
        for i, r in enumerate(rows):
            if r.get("contributor_id"):
                by_contrib[str(r["contributor_id"])].append(i)
        for contrib in sorted(by_contrib):
            idxs = by_contrib[contrib]
            if len(idxs) < int(p["contrib_min_samples"]):
                continue
            k_flag = sum(1 for i in idxs if sids[i] in flagged_samples)
            res = stats.binomtest(k_flag, len(idxs), p0,
                                  alternative="greater")
            pval = float(res.pvalue)
            if pval < float(p["contrib_p"]):
                n_contrib_flags += 1
                add(asset_id=contrib,
                    title=(f"Suspicious contributor anomaly rate (requires "
                           f"review): {contrib}"),
                    detection_method="contributor_binomial",
                    evidence={"contributor_id": contrib,
                              "n_samples": len(idxs),
                              "n_flagged": k_flag,
                              "flagged_rate": k_flag / len(idxs),
                              "global_flagged_rate": p0,
                              "p_value": pval,
                              "p_threshold": float(p["contrib_p"])},
                    confidence=min(0.90, 1.0 - pval),
                    severity="medium", disposition="REVIEW",
                    supported_attack_class=None,
                    limitations=("Elevated anomaly rate for one contributor "
                                 "is suspicious and requires review, not "
                                 "proof of malicious contribution; the "
                                 "contributor may simply submit harder or "
                                 "noisier data."))

    summary = {
        "scan_id": scan_id,
        "seed": seed,
        "params": _j(p),
        "methods_run": methods_run,
        "total_samples": n,
        "suspicious_samples": len(flagged_samples),
        "duplicate_groups": n_exact_groups + n_near_components,
        "ood_candidates": len(rep_anomaly_samples),
        "label_anomalies": n_label_anomalies,
        "contributor_flags": n_contrib_flags,
    }
    return findings, summary
