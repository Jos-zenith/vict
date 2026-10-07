"""DS1 pilot: the whole chain end to end, DS1 only (DS2 stays locked).

  python scripts/run_pilot.py --record 114   # Step 2: Base, one DS1-cal record
  python scripts/run_pilot.py                # Step 3: full pilot

Step 3, for each held-out noise type h (leave-one-noise-type-out):
  Robust_h  SVM on DS1-train clean + noisy copies of the other two types (Base's C)
  tables    window rows for every DS1-cal copy from Robust_h's decision values;
            risky = noise added a false V or lost a true V vs the paired clean copy
  dev       DS1-cal noisy copies of the other two types
  eval      DS1-cal noisy copies of type h
  Gc, Gcs   gates fitted on dev
  arms      Robust at the default threshold; Robust at a raised threshold; Robust
            gated by Gc / Gcs. Each arm's operating point is the one with the fewest
            false V calls whose V retention >= target x Robust's default retention.
            Gated arms search all (SVM threshold, gate cut-off) pairs, rejecting at
            most 1 - min_effective_coverage of the windows; the "<gate>@default"
            rows fix the SVM at its default threshold.
  modes     oracle  operating points chosen on eval itself: retention matched
                    exactly. This is the primary analysis.
            dev     chosen on dev, then applied to eval (do they transfer?)
Primary comparison: Gcs vs raised threshold, oracle, first retention target, with
false V/hour pooled per record over the three folds and the record-level bootstrap.
The coverage rule (>= min_effective_coverage windows kept) is checked per fold.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from vgate import config
from vgate.evaluation.stats import bootstrap_ci
from vgate.models.classifiers import make_svm, select_C
from vgate.models.gates import make_gate
from vgate.pipeline import Copy, ds1_copies, process, to_windows, training_data
from vgate.windows import WindowTable

OUT = config.RESULTS_DIR / "pilot"
WIN_H = config.pipeline()["window_s"] / 3600
ARMS = ("threshold", "Gc", "Gcs", "Gc@default", "Gcs@default")
MODES = ("oracle", "dev")


def _process(c: Copy) -> tuple[Copy, dict]:
    return c, process(c)


def process_all(copies: list[Copy]) -> dict[Copy, dict]:
    t = time.perf_counter()
    with ProcessPoolExecutor() as ex:
        data = dict(ex.map(_process, copies))
    print(f"processed {len(copies)} copies in {time.perf_counter() - t:.0f} s")
    return data


def fit(copies: list[Copy], data: dict[Copy, dict], C: float):
    X, y = (np.concatenate(p) for p in zip(*(training_data(data[c]) for c in copies), strict=True))
    return make_svm(C).fit(X, y)


def base_model(data: dict[Copy, dict]) -> tuple[object, float]:
    clean = [c for c in data if c.split == "train" and c.noise_type == "none"]
    parts = [training_data(data[c]) for c in clean]
    X = np.concatenate([p[0] for p in parts])
    y = np.concatenate([p[1] for p in parts])
    g = np.concatenate([np.full(len(p[1]), c.record) for c, p in zip(clean, parts, strict=True)])
    C = select_C(X, y, g)
    return make_svm(C).fit(X, y), C


def tables(model, copies: list[Copy], data: dict[Copy, dict]) -> WindowTable:
    """Window rows for the given copies; each record's clean copy labels its noisy ones."""
    out = []
    for r in sorted({c.record for c in copies}):
        mine = [c for c in copies if c.record == r]
        clean_copy = next(c for c in mine if c.copy == "clean")
        dec = {c: model.decision_function(data[c]["features"]) for c in mine}
        clean = to_windows(clean_copy, data[clean_copy], dec[clean_copy])
        out += [clean] + [to_windows(c, data[c], dec[c], clean) for c in mine if c.copy == "noisy"]
    return WindowTable.concat(out)


# --- operating points -----------------------------------------------------------
def retention(t: WindowTable, k: int, keep: np.ndarray) -> float:
    return float((t.n_true_v - t.lost_v[:, k])[keep].sum() / max(t.n_true_v.sum(), 1))


def operating_point(
    t: WindowTable, risk: np.ndarray | None, target: float, ks: np.ndarray, min_cov: float
) -> tuple[int, float]:
    """(SVM threshold index, gate cut-off) with the fewest false V at retention >= target.

    Windows with risk >= cut-off are rejected (no V calls). risk None: no gate.
    Searches every threshold in ``ks``; for each, rejects the riskiest windows first,
    as many as retention allows but never more than 1 - min_cov of the windows (the
    coverage rule constrains the operating point; it is not only checked afterwards).
    """
    total = max(t.n_true_v.sum(), 1)
    called = (t.n_true_v[:, None] - t.lost_v)[:, ks]
    fv = t.false_v[:, ks]
    if risk is None:
        ok = called.sum(0) / total >= target
        fv_k = np.where(ok, fv.sum(0), np.inf)
        j = int(np.argmin(fv_k)) if ok.any() else int(np.argmin(np.abs(ks - t.default_index)))
        return int(ks[j]), np.inf
    order = np.argsort(-risk, kind="stable")
    zero = np.zeros((1, len(ks)))
    ret = (called.sum(0) - np.vstack([zero, np.cumsum(called[order], 0)])) / total
    fv_left = fv.sum(0) - np.vstack([zero, np.cumsum(fv[order], 0)])
    m = (ret >= target).sum(0) - 1  # rejections allowed; -1 if even none reach target
    m = np.minimum(m, int((1 - min_cov) * len(risk)))
    best = np.where(m >= 0, fv_left[np.maximum(m, 0), np.arange(len(ks))], np.inf)
    if not np.isfinite(best).any():
        return t.default_index, np.inf
    j = int(np.argmin(best))
    cut = float(risk[order[m[j] - 1]]) if m[j] > 0 else np.inf
    return int(ks[j]), cut


def arm_rows(t: WindowTable, k: int, keep: np.ndarray) -> dict:
    """Per-record false V counts and hours, plus retention and coverage."""
    recs = np.unique(t.record)
    fv = t.false_v[:, k] * keep
    return {
        "records": recs.tolist(),
        "false_v": [int(fv[t.record == r].sum()) for r in recs],
        "hours": [float((t.record == r).sum() * WIN_H) for r in recs],
        "retention": retention(t, k, keep),
        "coverage": float(keep.mean()),
        "thr": float(t.thresholds[k]),
    }


def fold(h: str, data: dict[Copy, dict], C: float, base, targets: list[float]) -> dict:
    train = [c for c in data if c.split == "train" and c.noise_type != h]
    cal = [c for c in data if c.split == "cal"]
    t = tables(fit(train, data, C), cal, data)
    tb = tables(base, cal, data)
    dev = t.subset((t.copy == "noisy") & (t.noise_type != h))
    ev = t.subset(t.noise_type == h)
    ev_base = tb.subset(tb.noise_type == h)
    d = t.default_index
    all_k = np.arange(len(t.thresholds))
    min_cov = config.pipeline()["evaluation"]["min_effective_coverage"]

    risk = {}
    for name, sqi in (("Gc", False), ("Gcs", True)):
        g = make_gate().fit(dev.gate_features(sqi), dev.risky)
        risk[name] = {
            "dev": g.predict_proba(dev.gate_features(sqi))[:, 1],
            "oracle": g.predict_proba(ev.gate_features(sqi))[:, 1],
            "eval": g.predict_proba(ev.gate_features(sqi))[:, 1],
        }

    res = {
        "base": arm_rows(ev_base, d, np.ones(len(ev_base), bool)),
        "robust": arm_rows(ev, d, np.ones(len(ev), bool)),
        "risky_frac_dev": float(dev.risky.mean()),
        "targets": {},
    }
    for rho in targets:
        r = {}
        for mode in MODES:
            sel = ev if mode == "oracle" else dev
            target = rho * retention(sel, d, np.ones(len(sel), bool))
            for arm in ARMS:
                gate = arm.split("@")[0]
                ks = np.array([d]) if arm.endswith("@default") else all_k
                p_sel = None if arm == "threshold" else risk[gate][mode]
                k, cut = operating_point(sel, p_sel, target, ks, min_cov)
                keep = np.ones(len(ev), bool) if arm == "threshold" else risk[gate]["eval"] < cut
                r[f"{arm}_{mode}"] = arm_rows(ev, k, keep)
        res["targets"][str(rho)] = r

    by_snr = {}
    for s in sorted(set(ev.snr_db[~np.isnan(ev.snr_db)].tolist())) + [None]:
        m = np.isnan(ev.snr_db) if s is None else ev.snr_db == s
        by_snr["clean seg" if s is None else f"{s:g} dB"] = {
            "robust_fv_h": float(ev.false_v[m, d].sum() / (m.sum() * WIN_H)),
            "risky_frac": float(ev.risky[m].mean()),
        }
    res["by_snr"] = by_snr
    t.save(OUT / f"windows_cal_heldout_{h}.npz")
    return res


# --- reporting ------------------------------------------------------------------
def _get(d: dict, key: tuple[str, ...]) -> dict:
    for k in key:
        d = d[k]
    return d


def pooled(folds: dict[str, dict], key: tuple[str, ...]) -> tuple[np.ndarray, float]:
    """Per-record false V/hour pooled over folds, and the overall false V/hour."""
    rows = [_get(f, key) for f in folds.values()]
    fv = np.sum([r["false_v"] for r in rows], axis=0)
    hours = np.sum([r["hours"] for r in rows], axis=0)
    return fv / hours, fv.sum() / hours.sum()


def reduction(ref: dict, arm: dict) -> float:
    return 1 - sum(arm["false_v"]) / max(sum(ref["false_v"]), 1)


def full_pilot() -> None:
    ev_cfg = config.pipeline()["evaluation"]
    min_cov = ev_cfg["min_effective_coverage"]
    targets = config.pipeline()["thresholds"]["retention_targets"]
    data = process_all(ds1_copies())
    base, C = base_model(data)
    print(f"Base: C = {C}")
    folds = {}
    for h in config.splits()["noise"]["types"]:
        t = time.perf_counter()
        folds[h] = fold(h, data, C, base, targets)
        print(f"fold held-out {h}: {time.perf_counter() - t:.0f} s")
    types = list(folds)

    print("\nRisky (gate label) fraction of dev windows: "
          + ", ".join(f"{h} fold {f['risky_frac_dev']:.1%}" for h, f in folds.items()))
    print("\nFalse V/h on held-out noise, default threshold (pooled over folds)")
    for name, key in (("Base (clean-trained)", ("base",)), ("Robust", ("robust",))):
        print(f"   {name:22s} {pooled(folds, key)[1]:7.1f}  per fold: " + "  ".join(
            f"{h} {_get(f, key)['retention']:.3f} ret" for h, f in folds.items()))

    summary = {"C": C, "folds": folds, "comparisons": {}}
    for rho in targets:
        for mode in MODES:
            print(f"\n-- target {rho} x Robust default retention, {mode} operating points "
                  f"{'(PRIMARY)' if mode == 'oracle' and rho == targets[0] else ''}")
            print(f"   {'arm':12s} {'FV/h':>7}  " + "  ".join(
                f"{h + ': ret / kept / thr / vs thr':>34s}" for h in types))
            for arm in ARMS:
                key = ("targets", str(rho), f"{arm}_{mode}")
                cells = []
                for f in folds.values():
                    a = _get(f, key)
                    vs = reduction(_get(f, ("targets", str(rho), f"threshold_{mode}")), a)
                    flag = "!" if a["coverage"] < min_cov else " "
                    cells.append(f"{a['retention']:.3f} / {a['coverage']:4.0%}{flag}/ "
                                 f"{a['thr']:+.2f} / {vs:+6.1%}")
                print(f"   {arm:12s} {pooled(folds, key)[1]:7.1f}  " + "  ".join(
                    f"{c:>34s}" for c in cells))
    print(f"   (! = fold keeps fewer than {min_cov:.0%} of windows: fails the coverage rule)")

    rho = str(targets[0])
    print(f"\nRelative reduction in false V/h, target {rho}, record bootstrap over folds "
          f"(95 % CI; meaningful >= {ev_cfg['min_meaningful_effect']:.0%})")
    comps = [("Robust vs Base", ("base",), ("robust",))]
    for mode in MODES:
        for g in ("Gcs", "Gc", "Gcs@default"):
            comps.append((f"{g} vs raised threshold ({mode})",
                          ("targets", rho, f"threshold_{mode}"), ("targets", rho, f"{g}_{mode}")))
        comps.append((f"Gcs vs Gc ({mode})", ("targets", rho, f"Gc_{mode}"),
                      ("targets", rho, f"Gcs_{mode}")))
    for name, ref_key, arm_key in comps:
        ref, _ = pooled(folds, ref_key)
        arm, _ = pooled(folds, arm_key)
        est, lo, hi = bootstrap_ci(ref, arm, n=ev_cfg["bootstrap_resamples"], seed=ev_cfg["seed"])
        per_fold = {h: reduction(_get(f, ref_key), _get(f, arm_key)) for h, f in folds.items()}
        cov = {h: _get(f, arm_key)["coverage"] for h, f in folds.items()}
        cov_ok = all(c >= min_cov for c in cov.values())
        summary["comparisons"][name] = {"estimate": est, "ci95": [lo, hi], "per_fold": per_fold,
                                        "coverage": cov, "coverage_ok_every_fold": cov_ok}
        print(f"   {name:36s} {est:+7.1%}  [{lo:+.1%}, {hi:+.1%}]  per fold "
              + " ".join(f"{h} {v:+.0%}" for h, v in per_fold.items())
              + ("" if cov_ok else "  COVERAGE FAIL"))

    print("\nRobust (default) by SNR on held-out noise: false V/h | risky window fraction")
    for h, f in folds.items():
        print(f"   {h}: " + "  ".join(
            f"{k}: {v['robust_fv_h']:.0f}|{v['risky_frac']:.2f}" for k, v in f["by_snr"].items()))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    print(f"\nwrote {OUT / 'summary.json'}")


def one_record(record: int, noise: str) -> None:
    if record not in config.splits()["ds1"]["cal"]:
        raise SystemExit(f"{record} is not a DS1-cal record")
    cal = [Copy(record, "cal", "none"), Copy(record, "cal", noise, 0)]
    train = [Copy(r, "train", "none") for r in config.splits()["ds1"]["train"]]
    data = process_all(train + cal)
    base, C = base_model(data)
    print(f"Base: C = {C}")
    t = tables(base, cal, data)
    d = t.default_index
    for cp in ("clean", "noisy"):
        s = t.subset(t.copy == cp)
        keep = np.ones(len(s), bool)
        fvh = s.false_v[:, d].sum() / (len(s) * WIN_H)
        print(f"record {record} {cp:5s}: {fvh:6.1f} false V/h, "
              f"V retention {retention(s, d, keep):.3f}, {s.risky.mean():.0%} risky windows")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", type=int, help="Step 2: one DS1-cal record with Base")
    ap.add_argument("--noise", default="em")
    a = ap.parse_args()
    one_record(a.record, a.noise) if a.record else full_pilot()


if __name__ == "__main__":
    main()
