"""DS1 pilot: the whole chain end to end, DS1 only (DS2 stays locked).

  python scripts/run_pilot.py --record 114   # Step 2: Base, one DS1-cal record
  python scripts/run_pilot.py                # Step 3: full pilot

Step 3, for each held-out noise type h (leave-one-noise-type-out):
  Robust_h  SVM on DS1-train clean + noisy copies of the other two types (Base's C)
  tables    window rows for every DS1-cal copy, from Robust_h's decision values
  dev       DS1-cal windows of the clean copy and the other two types
  eval      DS1-cal windows of noise type h
  Gc, Gcs   gates fitted on dev (label: risky)
  arms      Robust at the default threshold; Robust at a raised threshold; Robust
            gated by Gc; gated by Gcs. Raised threshold and gate cut-offs are set on
            dev so V retention = target x Robust's default retention, then applied
            to eval. ("oracle" rows set them on eval itself, exactly matched.)
False V calls/hour are pooled per record over the three folds and compared with
the record-level bootstrap.
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
    return WindowTable.concat(
        [to_windows(c, data[c], model.decision_function(data[c]["features"])) for c in copies]
    )


# --- operating points -----------------------------------------------------------
def retention_at(t: WindowTable, k: int, keep: np.ndarray | None = None) -> float:
    keep = np.ones(len(t), bool) if keep is None else keep
    return float((t.n_true_v - t.lost_v[:, k])[keep].sum() / max(t.n_true_v.sum(), 1))


def threshold_for(t: WindowTable, target: float) -> int:
    """Highest threshold index whose retention is still >= target."""
    ok = [k for k in range(len(t.thresholds)) if retention_at(t, k) >= target]
    return max(ok) if ok else t.default_index


def gate_cutoff(t: WindowTable, risk: np.ndarray, target: float) -> float:
    """Lowest risk cut-off (reject risk >= cut-off) keeping retention >= target."""
    d = t.default_index
    kept_v = (t.n_true_v - t.lost_v[:, d]).astype(float)
    order = np.argsort(-risk)
    retained = kept_v.sum() - np.cumsum(kept_v[order])
    ok = np.flatnonzero(retained / max(t.n_true_v.sum(), 1) >= target)
    if len(ok) == 0:
        return np.inf
    m = ok[-1] + 1  # reject the m riskiest windows
    return float(risk[order[m - 1]]) if m < len(order) else -np.inf


def arm_rows(t: WindowTable, k: int, keep: np.ndarray) -> dict:
    """Per-record false V counts and hours, plus pooled retention and coverage."""
    recs = np.unique(t.record)
    fv = t.false_v[:, k] * keep
    return {
        "records": recs.tolist(),
        "false_v": [int(fv[t.record == r].sum()) for r in recs],
        "hours": [float((t.record == r).sum() * WIN_H) for r in recs],
        "retention": retention_at(t, k, keep),
        "coverage": float(keep.mean()),
    }


def fold(h: str, data: dict[Copy, dict], C: float, base, targets: list[float]) -> dict:
    train = [c for c in data if c.split == "train" and c.noise_type != h]
    cal = [c for c in data if c.split == "cal"]
    robust = fit(train, data, C)
    t = tables(robust, cal, data)
    tb = tables(base, cal, data)
    dev, ev = t.subset(t.noise_type != h), t.subset(t.noise_type == h)
    ev_base = tb.subset(tb.noise_type == h)
    d = t.default_index

    gates = {}
    for name, sqi in (("Gc", False), ("Gcs", True)):
        g = make_gate().fit(dev.gate_features(sqi), dev.risky)
        gates[name] = (
            g.predict_proba(dev.gate_features(sqi))[:, 1],
            g.predict_proba(ev.gate_features(sqi))[:, 1],
        )

    all_keep = np.ones(len(ev), bool)
    res = {
        "base": arm_rows(ev_base, d, np.ones(len(ev_base), bool)),
        "robust": arm_rows(ev, d, all_keep),
        "targets": {},
    }
    for rho in targets:
        r = {}
        for mode, src in (("dev", dev), ("oracle", ev)):
            target = rho * retention_at(src, d)
            k = threshold_for(src, target)
            r[f"threshold_{mode}"] = {**arm_rows(ev, k, all_keep), "thr": float(t.thresholds[k])}
            for name, (p_dev, p_ev) in gates.items():
                cut = gate_cutoff(src, p_dev if mode == "dev" else p_ev, target)
                r[f"{name}_{mode}"] = arm_rows(ev, d, p_ev < cut)
        res["targets"][str(rho)] = r

    snr_rows = {}
    for s in sorted(set(ev.snr_db[~np.isnan(ev.snr_db)].tolist())) + [None]:
        m = np.isnan(ev.snr_db) if s is None else ev.snr_db == s
        snr_rows["clean seg" if s is None else f"{s:g} dB"] = {
            "robust_fv_h": float(ev.false_v[m, d].sum() / (m.sum() * WIN_H)),
            "risky_frac": float(ev.risky[m].mean()),
        }
    res["by_snr"] = snr_rows
    t.save(OUT / f"windows_cal_heldout_{h}.npz")
    return res


def pooled(folds: dict[str, dict], key: tuple[str, ...]) -> tuple[np.ndarray, float, float, float]:
    """Per-record false V/hour pooled over folds, and mean retention / coverage."""
    rows = [_get(f, key) for f in folds.values()]
    fv = np.sum([r["false_v"] for r in rows], axis=0)
    hours = np.sum([r["hours"] for r in rows], axis=0)
    retention = float(np.mean([r["retention"] for r in rows]))
    coverage = float(np.mean([r["coverage"] for r in rows]))
    return fv / hours, fv.sum() / hours.sum(), retention, coverage


def _get(d: dict, key: tuple[str, ...]) -> dict:
    for k in key:
        d = d[k]
    return d


def full_pilot() -> None:
    ev = config.pipeline()["evaluation"]
    targets = config.pipeline()["thresholds"]["retention_targets"]
    data = process_all(ds1_copies())
    base, C = base_model(data)
    print(f"Base: C = {C}")
    folds = {}
    for h in config.splits()["noise"]["types"]:
        t = time.perf_counter()
        folds[h] = fold(h, data, C, base, targets)
        print(f"fold held-out {h}: {time.perf_counter() - t:.0f} s")

    print("\nFalse V calls/hour on held-out noise (DS1-cal, pooled over the 3 folds)")
    print(f"{'arm':28s} {'FV/h':>7} {'retention':>9} {'coverage':>8}")
    for name, key in (
        ("Base (clean-trained)", ("base",)),
        ("Robust, default threshold", ("robust",)),
    ):
        _, tot, ret, cov = pooled(folds, key)
        print(f"{name:28s} {tot:7.2f} {ret:9.3f} {cov:8.3f}")
    summary = {"C": C, "folds": folds, "comparisons": {}}
    for rho in targets:
        print(f"-- retention target {rho} x Robust default")
        for mode in ("dev", "oracle"):
            for arm in ("threshold", "Gc", "Gcs"):
                _, tot, ret, cov = pooled(folds, ("targets", str(rho), f"{arm}_{mode}"))
                print(f"   {arm + ' (' + mode + ')':25s} {tot:7.2f} {ret:9.3f} {cov:8.3f}")

    meaningful, min_cov = ev["min_meaningful_effect"], ev["min_effective_coverage"]
    print(
        "\nRelative reduction in false V/hour (record bootstrap, 95 % CI); "
        f"meaningful >= {meaningful:.0%}, coverage >= {min_cov:.0%}"
    )
    rho = str(targets[0])
    comps = [
        ("Robust vs Base", ("base",), ("robust",)),
        *[
            (
                f"{g} vs raised threshold ({m})",
                ("targets", rho, f"threshold_{m}"),
                ("targets", rho, f"{g}_{m}"),
            )
            for m in ("dev", "oracle")
            for g in ("Gc", "Gcs")
        ],
        *[
            (f"Gcs vs Gc ({m})", ("targets", rho, f"Gc_{m}"), ("targets", rho, f"Gcs_{m}"))
            for m in ("dev", "oracle")
        ],
    ]
    for name, ref_key, arm_key in comps:
        ref, *_ = pooled(folds, ref_key)
        arm, _, _, cov = pooled(folds, arm_key)
        est, lo, hi = bootstrap_ci(ref, arm, n=ev["bootstrap_resamples"], seed=ev["seed"])
        summary["comparisons"][name] = {"estimate": est, "ci95": [lo, hi], "coverage": cov}
        print(f"   {name:34s} {est:+7.1%}  [{lo:+.1%}, {hi:+.1%}]")

    print("\nRobust (default) by SNR on held-out noise: false V/h | risky window fraction")
    for h, f in folds.items():
        print(
            f"   {h}: "
            + "  ".join(
                f"{k}: {v['robust_fv_h']:.1f}|{v['risky_frac']:.2f}" for k, v in f["by_snr"].items()
            )
        )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    print(f"\nwrote {OUT / 'summary.json'}")


def one_record(record: int, noise: str) -> None:
    cal = [Copy(record, "cal", "none"), Copy(record, "cal", noise, 0)]
    train = [Copy(r, "train", "none") for r in config.splits()["ds1"]["train"]]
    if record not in config.splits()["ds1"]["cal"]:
        raise SystemExit(f"{record} is not a DS1-cal record")
    data = process_all(train + cal)
    base, C = base_model(data)
    print(f"Base: C = {C}")
    for c in cal:
        t = to_windows(c, data[c], base.decision_function(data[c]["features"]))
        d = t.default_index
        hours = len(t) * WIN_H
        print(
            f"record {record} {c.copy:5s} {c.noise_type:4s}: {t.false_v[:, d].sum() / hours:6.1f} "
            f"false V/h, V retention {retention_at(t, d):.3f}, {t.risky.mean():.0%} risky windows"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", type=int, help="Step 2: one DS1-cal record with Base")
    ap.add_argument("--noise", default="em")
    a = ap.parse_args()
    one_record(a.record, a.noise) if a.record else full_pilot()


if __name__ == "__main__":
    main()
