"""Phase 1 study: can the fallback design be frozen? (docs/qsqi_deferral_plan.md)

  python scripts/run_qsqi_deferral.py

DS1 only, same folds as the calibration study. Writes docs/qsqi_deferral_results.md.
"""

from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from vgate import config
from vgate.evaluation.operating import defer_cutoff, highest_threshold, retention
from vgate.models.classifiers import make_svm, select_C
from vgate.models.gates import make_gate
from vgate.pipeline import Copy, ds1_copies, process, training_data, window_tables
from vgate.windows import WindowTable

OUT = config.ROOT / "docs" / "qsqi_deferral_results.md"
WIN_H = config.pipeline()["window_s"] / 3600
MIN_BEATS = config.pipeline()["windowing"]["min_beats"]
RHO, Q_APRIORI, D1_KEEP = 0.9, 0.8, 0.85
METHODS = ("D0 a priori", "D1 calibrated deferral", "D2 calibrated threshold")
FIELDS = ("false_v", "called_v", "true_v", "kept", "windows")


def qsqi(t: WindowTable) -> np.ndarray:
    return np.exp(t.log_qsqi)


def keep_mask(t: WindowTable, q: float) -> np.ndarray:
    return (qsqi(t) >= q) & (t.n_beats >= MIN_BEATS)


def d1_cutoff(t: WindowTable) -> float:
    """Largest q* at which every noise type keeps >= D1_KEEP of its windows."""
    best = 0.0
    for q in np.unique(qsqi(t)):
        k = keep_mask(t, q)
        if min(k[t.noise_type == n].mean() for n in np.unique(t.noise_type)) >= D1_KEEP:
            best = float(q)
        else:
            break
    return best


def d2_threshold(t: WindowTable) -> int:
    """Highest SVM threshold with retention (D0 deferral applied) >= RHO x default."""
    keep = keep_mask(t, Q_APRIORI)
    target = RHO * retention(t, t.default_index)
    ok = [k for k in range(len(t.thresholds)) if retention(t, k, keep) >= target]
    return max(ok) if ok else t.default_index


def counts(t: WindowTable, k: int, keep: np.ndarray) -> dict:
    return {"false_v": int((t.false_v[:, k] * keep).sum()),
            "called_v": int(((t.n_true_v - t.lost_v[:, k]) * keep).sum()),
            "true_v": int(t.n_true_v.sum()), "kept": int(keep.sum()),
            "windows": len(t)}  # fmt: skip


def run_fold(h: str, r: int, noisy: WindowTable) -> dict:
    d = noisy.default_index
    calib = noisy.subset((noisy.record != r) & (noisy.noise_type != h))
    test = noisy.subset((noisy.record == r) & (noisy.noise_type == h))
    all_kept = np.ones(len(test), bool)
    settings = {
        "D0 a priori": (d, Q_APRIORI),
        "D1 calibrated deferral": (d, d1_cutoff(calib)),
        "D2 calibrated threshold": (d2_threshold(calib), Q_APRIORI),
    }
    out = {"robust": counts(test, d, all_kept)}
    for name, (k, q) in settings.items():
        keep = keep_mask(test, q)
        low_q, few = qsqi(test) < q, test.n_beats < MIN_BEATS
        out[name] = {"with": counts(test, k, keep), "without": counts(test, k, all_kept),
                     "thr": float(test.thresholds[k]), "q": q,
                     "by_qsqi_only": int((low_q & ~few).sum()),
                     "by_beats": int(few.sum())}  # fmt: skip
    # context: raised threshold and Gcs, calibrated as method M0 of the calibration study
    target = RHO * retention(calib, d)
    out["raised threshold (M0)"] = counts(test, highest_threshold(calib, target), all_kept)
    gate = make_gate().fit(calib.gate_features(True), calib.risky)
    cut = defer_cutoff(calib, gate.predict_proba(calib.gate_features(True))[:, 1], target, d,
                       0.8, groups=calib.noise_type)  # fmt: skip
    out["Gcs (M0)"] = counts(test, d, gate.predict_proba(test.gate_features(True))[:, 1] < cut)
    return {"h": h, "r": r, **out}


def _xy(copies: list[Copy], data: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    parts = [training_data(data[c]) for c in copies]
    g = [np.full(len(p[1]), c.record) for c, p in zip(copies, parts, strict=True)]
    return (np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts]),
            np.concatenate(g))  # fmt: skip


def main() -> None:
    t0 = time.perf_counter()
    copies = ds1_copies()
    with ProcessPoolExecutor() as ex:
        data = dict(zip(copies, ex.map(process, copies), strict=True))
    X, y, g = _xy([c for c in copies if c.split == "train" and c.copy == "clean"], data)
    C = select_C(X, y, g)
    cal_copies = [c for c in copies if c.split == "cal"]
    folds = []
    for h in config.splits()["noise"]["types"]:
        X, y, _ = _xy([c for c in copies if c.split == "train" and c.noise_type != h], data)
        t = window_tables(make_svm(C).fit(X, y), cal_copies, data)
        noisy = t.subset(t.copy == "noisy")
        folds += [run_fold(h, r, noisy) for r in sorted(set(t.record))]
    print(f"C = {C}; {len(folds)} folds in {time.perf_counter() - t0:.0f} s")
    report(folds)


def _sum(rows: list[dict]) -> dict:
    return {f: sum(x[f] for x in rows) for f in FIELDS}


def _m(c: dict) -> tuple[float, float, float]:
    return (c["false_v"] / (c["windows"] * WIN_H), c["called_v"] / max(c["true_v"], 1),
            c["kept"] / c["windows"])  # fmt: skip


def _pf(x: bool) -> str:
    return "pass" if x else "FAIL"


def report(folds: list[dict]) -> None:
    ev = config.pipeline()["evaluation"]
    types = config.splits()["noise"]["types"]
    lines = ["# Phase 1 study: can the fallback design be frozen? Results", "",
             "Pre-registered in `docs/qsqi_deferral_plan.md` (committed before this run). DS1 "
             "only; per held-out noise type, pooled over its six record folds. FV/h = false V "
             "calls per hour; ret = V retention; kept = windows kept.", ""]  # fmt: skip
    passed = {}
    for name in METHODS:
        lines += [f"## {name}", "",
                  "| held-out | SVM thr (mean) | q* (mean) | kept | ret (floor) | "
                  "FV/h with / without deferral | reduction | deferred: qSQI only / few beats | "
                  "T1 | T2 | T3 | T4 |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
        ok_all = True
        for h in types:
            fs = [f for f in folds if f["h"] == h]
            floor = RHO * _m(_sum([f["robust"] for f in fs]))[1] - 0.02
            w = _m(_sum([f[name]["with"] for f in fs]))
            wo = _m(_sum([f[name]["without"] for f in fs]))
            red = 1 - w[0] / wo[0] if wo[0] else 0.0
            deferred = 1 - w[2]
            n = sum(f[name]["with"]["windows"] for f in fs)
            by_q = sum(f[name]["by_qsqi_only"] for f in fs) / n
            by_b = sum(f[name]["by_beats"] for f in fs) / n
            t1, t2 = w[2] >= ev["min_effective_coverage"], w[1] >= floor
            t3, t4 = red >= ev["min_meaningful_effect"], red > deferred
            ok_all &= t1 and t2 and t3 and t4
            lines.append(
                f"| {h} | {np.mean([f[name]['thr'] for f in fs]):+.2f} | "
                f"{np.mean([f[name]['q'] for f in fs]):.3f} | {w[2]:.1%} | {w[1]:.3f} "
                f"({floor:.3f}) | {w[0]:.0f} / {wo[0]:.0f} | {red:+.1%} | {by_q:.1%} / {by_b:.1%} "
                f"| {_pf(t1)} | {_pf(t2)} | {_pf(t3)} | {_pf(t4)} |")  # fmt: skip
        passed[name] = ok_all
        lines += ["", f"**{name}: {'can be frozen' if ok_all else 'cannot be frozen'}.**", ""]

    lines += ["## Context (not used to pass or fail)", "",
              "| held-out | Robust default: FV/h, ret | raised threshold (M0): FV/h, ret | "
              "Gcs (M0): FV/h, ret, kept |", "|---|---|---|---|"]  # fmt: skip
    for h in types:
        fs = [f for f in folds if f["h"] == h]
        rb, rt, gc = (_m(_sum([f[a] for f in fs])) for a in
                      ("robust", "raised threshold (M0)", "Gcs (M0)"))  # fmt: skip
        lines.append(f"| {h} | {rb[0]:.0f}, {rb[1]:.3f} | {rt[0]:.0f}, {rt[1]:.3f} | "
                     f"{gc[0]:.0f}, {gc[1]:.3f}, {gc[2]:.0%} |")  # fmt: skip
    first = next((n for n in METHODS if passed[n]), None)
    decision = (f"**The fallback design can be frozen with {first}** (decision rule 1). Selected "
                "on DS1, so not a claim until the strap-noise re-test." if first else
                "**No method passes** (decision rule 2): the fallback cannot be frozen with fixed "
                "settings. The team chooses between threshold-only (retention drift documented) "
                "and a pre-registered adaptive-calibration study.")  # fmt: skip
    lines += ["", "## Decision", "", decision, ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
