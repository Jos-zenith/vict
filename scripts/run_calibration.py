"""Phase 1 calibration-transfer study, as pre-registered in docs/calibration_plan.md.

  python scripts/run_calibration.py

DS1 only. For each held-out noise type h and DS1-cal record r, every setting is fixed
on the other cal records and the other two noise types, then applied to record r with
noise h. Writes docs/calibration_results.md.
"""

from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from vgate import config
from vgate.evaluation.operating import defer_cutoff, highest_threshold, retention
from vgate.evaluation.stats import bootstrap_ci
from vgate.models.classifiers import make_svm, select_C
from vgate.models.gates import make_gate
from vgate.pipeline import Copy, ds1_copies, process, training_data, window_tables
from vgate.windows import WindowTable

OUT = config.ROOT / "docs" / "calibration_results.md"
WIN_H = config.pipeline()["window_s"] / 3600
RHO = 0.9
METHODS = {  # name: (rho on the calibration set, coverage cap per noise type, P(risky) cut)
    "M0 frozen rule": (0.90, 0.80, None),
    "M1 margin": (0.92, 0.85, None),
    "M2 probability": (0.90, None, 0.5),
}
ARMS = ("threshold", "Gc", "Gcs")
FIELDS = ("false_v", "called_v", "true_v", "kept", "windows")


def _xy(copies: list[Copy], data: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    parts = [training_data(data[c]) for c in copies]
    g = [np.full(len(p[1]), c.record) for c, p in zip(copies, parts, strict=True)]
    return (np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts]),
            np.concatenate(g))  # fmt: skip


def counts(t: WindowTable, k: int, keep: np.ndarray) -> dict:
    return {"false_v": int((t.false_v[:, k] * keep).sum()),
            "called_v": int(((t.n_true_v - t.lost_v[:, k]) * keep).sum()),
            "true_v": int(t.n_true_v.sum()), "kept": int(keep.sum()),
            "windows": len(t)}  # fmt: skip


def run_fold(h: str, r: int, noisy: WindowTable) -> dict:
    d = noisy.default_index
    calib = noisy.subset((noisy.record != r) & (noisy.noise_type != h))
    test = noisy.subset((noisy.record == r) & (noisy.noise_type == h))
    gates = {g: make_gate().fit(calib.gate_features(g == "Gcs"), calib.risky)
             for g in ("Gc", "Gcs")}  # fmt: skip
    risk = {g: (m.predict_proba(calib.gate_features(g == "Gcs"))[:, 1],
                m.predict_proba(test.gate_features(g == "Gcs"))[:, 1])
            for g, m in gates.items()}  # fmt: skip
    out = {"robust": counts(test, d, np.ones(len(test), bool))}
    for name, (rho, cap, p_cut) in METHODS.items():
        target = rho * retention(calib, d)
        k = highest_threshold(calib, target)
        res = {"threshold": counts(test, k, np.ones(len(test), bool)),
               "thr": float(test.thresholds[k])}  # fmt: skip
        for g, (rc, rt) in risk.items():
            cut = p_cut if p_cut is not None else defer_cutoff(
                calib, rc, target, d, cap, groups=calib.noise_type)  # fmt: skip
            res[g] = counts(test, d, rt < cut)
        out[name] = res
    return {"h": h, "r": r, **out}


def main() -> None:
    t0 = time.perf_counter()
    copies = ds1_copies()
    with ProcessPoolExecutor() as ex:
        data = dict(zip(copies, ex.map(process, copies), strict=True))
    X, y, g = _xy([c for c in copies if c.split == "train" and c.copy == "clean"], data)
    C = select_C(X, y, g)
    cal_copies = [c for c in copies if c.split == "cal"]
    cal_records = sorted({c.record for c in cal_copies})
    folds = []
    for h in config.splits()["noise"]["types"]:
        X, y, _ = _xy([c for c in copies if c.split == "train" and c.noise_type != h], data)
        robust = make_svm(C).fit(X, y)
        t = window_tables(robust, cal_copies, data)
        noisy = t.subset(t.copy == "noisy")
        folds += [run_fold(h, r, noisy) for r in cal_records]
    print(f"C = {C}; {len(folds)} folds in {time.perf_counter() - t0:.0f} s")
    report(folds, cal_records)


def _sum(rows: list[dict]) -> dict:
    return {f: sum(x[f] for x in rows) for f in FIELDS}


def _metrics(c: dict) -> tuple[float, float, float]:
    hours = c["windows"] * WIN_H
    return c["false_v"] / hours, c["called_v"] / max(c["true_v"], 1), c["kept"] / c["windows"]


def _pf(x: bool) -> str:
    return "pass" if x else "FAIL"


def report(folds: list[dict], recs: list[int]) -> None:
    ev = config.pipeline()["evaluation"]
    types = config.splits()["noise"]["types"]
    lines = ["# Phase 1 calibration study: results", "",
             "Pre-registered in `docs/calibration_plan.md` (committed before this run). "
             "DS1 only; per held-out noise type, pooled over its six record folds. "
             "FV/h = false V calls per hour; ret = V retention; kept = windows kept. "
             "T2 is shown per arm (threshold/Gcs).", ""]  # fmt: skip
    verdicts = {}
    for name in METHODS:
        lines += [f"## {name}", "",
                  "| held-out | target ret | threshold: FV/h, ret | Gc: FV/h, ret, kept | "
                  "Gcs: FV/h, ret, kept | Gcs vs threshold (95 % CI) | Gcs vs Gc | "
                  "T1 | T2 thr/Gcs | T3 |",
                  "|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
        mins, passes = [], []
        for h in types:
            fs = [f for f in folds if f["h"] == h]
            target = RHO * _metrics(_sum([f["robust"] for f in fs]))[1]
            m = {a: _metrics(_sum([f[name][a] for f in fs])) for a in ARMS}
            per_rec = {a: np.array([_metrics(f[name][a])[0] for f in fs]) for a in ARMS}
            est, lo, hi = bootstrap_ci(per_rec["threshold"], per_rec["Gcs"],
                                       n=ev["bootstrap_resamples"], seed=ev["seed"])  # fmt: skip
            gg = 1 - m["Gcs"][0] / m["Gc"][0] if m["Gc"][0] else float("nan")
            t1 = m["Gcs"][2] >= ev["min_effective_coverage"]
            t2_thr, t2_gcs = (m[a][1] >= target - 0.02 for a in ("threshold", "Gcs"))
            t2 = t2_thr and t2_gcs
            t3 = m["Gcs"][0] < m["threshold"][0]
            passes.append(t1 and t2 and t3)
            mins.append(est)
            lines.append(
                f"| {h} | {target:.3f} | {m['threshold'][0]:.0f}, {m['threshold'][1]:.3f} | "
                f"{m['Gc'][0]:.0f}, {m['Gc'][1]:.3f}, {m['Gc'][2]:.0%} | "
                f"{m['Gcs'][0]:.0f}, {m['Gcs'][1]:.3f}, {m['Gcs'][2]:.0%} | "
                f"{est:+.1%} ({lo:+.0%}, {hi:+.0%}) | {gg:+.1%} | "
                + f"{_pf(t1)} | {_pf(t2_thr)}/{_pf(t2_gcs)} | {_pf(t3)} |")  # fmt: skip
        verdicts[name] = (all(passes), min(mins))
        lines += ["", f"**{name}: {'transfers' if all(passes) else 'does not transfer'}** "
                  f"(smallest Gcs-vs-threshold reduction {min(mins):+.1%}).", ""]  # fmt: skip
    ok = [n for n in METHODS if verdicts[n][0]]
    if ok:
        lead = max(ok, key=lambda n: (verdicts[n][1], -list(METHODS).index(n)))
        decision = (f"**Lead calibration: {lead}** (decision rule 1: transfers, largest minimum "
                    "reduction). Selected on DS1, so not a claim: it needs the fresh-data re-test.")
    else:
        decision = ("**No method transfers** (decision rule 2): no fixed-cut-off Gcs design is "
                    "claimed; the design falls back to threshold plus detector-quality deferral, "
                    "with Gcs kept as an option.")
    lines += ["## Decision", "", decision, ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
