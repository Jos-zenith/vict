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
  arms      raised threshold: the highest SVM threshold with V retention >= target
            (target = rho x Robust's default retention). Gated arms: the (SVM
            threshold, gate cut-off) pair with the fewest false V at retention >=
            target, deferring at most 1 - cap of the windows, for each coverage cap
            in [evaluation] coverage_curve. "<gate>@default" fixes the SVM threshold.
  modes     oracle  operating points chosen on eval itself (retention matched
                    exactly) -- the primary analysis
            dev     chosen on dev and applied to eval (deployment-like transfer)
Results are kept per record so every figure can be given with and without the
"clean-error" records: those whose clean copy already has more than
[evaluation] clean_error_fv_h false V/h under Robust (classifier errors on clean
signal, which no noise gate can or should remove).
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from vgate import config
from vgate.evaluation.operating import arm_rows as _arm_rows
from vgate.evaluation.operating import operating_point, retention
from vgate.evaluation.stats import bootstrap_ci
from vgate.models.classifiers import make_svm, select_C
from vgate.models.gates import make_gate
from vgate.pipeline import Copy, ds1_copies, process, to_windows, training_data
from vgate.windows import WindowTable

OUT = config.RESULTS_DIR / "pilot"
WIN_H = config.pipeline()["window_s"] / 3600
GATES = ("Gc", "Gcs", "Gc@default", "Gcs@default")
MODES = ("oracle", "dev")
EVAL = config.pipeline()["evaluation"]
CAPS = [float(c) for c in EVAL["coverage_curve"]]
RULE = float(EVAL["min_effective_coverage"])


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


def arm_rows(t: WindowTable, k: int, keep: np.ndarray) -> dict:
    return _arm_rows(t, k, keep, WIN_H)


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

    risk = {}
    for name, sqi in (("Gc", False), ("Gcs", True)):
        g = make_gate().fit(dev.gate_features(sqi), dev.risky)
        risk[name] = {"dev": g.predict_proba(dev.gate_features(sqi))[:, 1],
                      "oracle": g.predict_proba(ev.gate_features(sqi))[:, 1]}  # fmt: skip

    clean = t.subset(t.copy == "clean")
    res = {
        "base": arm_rows(ev_base, d, np.ones(len(ev_base), bool)),
        "robust": arm_rows(ev, d, np.ones(len(ev), bool)),
        "clean_fv_h": {int(r): float(clean.false_v[clean.record == r, d].sum()
                                     / ((clean.record == r).sum() * WIN_H))
                       for r in np.unique(clean.record)},
        "risky_frac_dev": float(dev.risky.mean()),
        "targets": {},
    }  # fmt: skip
    for rho in targets:
        per_mode = {}
        for mode in MODES:
            sel = ev if mode == "oracle" else dev
            target = rho * retention(sel, d)
            k, _ = operating_point(sel, None, target, all_k, 1.0)
            arms: dict = {"threshold": arm_rows(ev, k, np.ones(len(ev), bool))}
            for arm in GATES:
                gate = arm.split("@")[0]
                ks = np.array([d]) if arm.endswith("@default") else all_k
                arms[arm] = {}
                for cap in CAPS:
                    k, cut = operating_point(sel, risk[gate][mode], target, ks, cap)
                    arms[arm][f"{cap:.2f}"] = arm_rows(ev, k, risk[gate]["oracle"] < cut)
            per_mode[mode] = arms
        res["targets"][str(rho)] = per_mode

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


# --- aggregation ----------------------------------------------------------------
def _get(d: dict, key: tuple[str, ...]) -> dict:
    for k in key:
        d = d[k]
    return d


def agg(rows: list[dict], recs: list[int]) -> dict:
    """Sum per-record counts over folds for the given records."""
    idx = [rows[0]["records"].index(r) for r in recs]
    tot = {n: np.sum([np.asarray(x[n])[idx] for x in rows], axis=0)
           for n in ("false_v", "called_v", "true_v", "kept", "windows")}  # fmt: skip
    hours = tot["windows"] * WIN_H
    return {
        "fvh_rec": tot["false_v"] / hours,
        "fvh": tot["false_v"].sum() / hours.sum(),
        "retention": tot["called_v"].sum() / max(tot["true_v"].sum(), 1),
        "coverage": tot["kept"].sum() / tot["windows"].sum(),
    }


def compare(folds: dict, ref_key: tuple, arm_key: tuple, recs: list[int]) -> dict:
    """Pooled relative reduction with record bootstrap, plus per-fold point estimates."""
    ref = agg([_get(f, ref_key) for f in folds.values()], recs)
    arm = agg([_get(f, arm_key) for f in folds.values()], recs)
    est, lo, hi = bootstrap_ci(ref["fvh_rec"], arm["fvh_rec"], n=EVAL["bootstrap_resamples"],
                               seed=EVAL["seed"])  # fmt: skip
    per_fold = {h: 1 - agg([_get(f, arm_key)], recs)["fvh"] / agg([_get(f, ref_key)], recs)["fvh"]
                for h, f in folds.items()}  # fmt: skip
    cov = {h: agg([_get(f, arm_key)], recs)["coverage"] for h, f in folds.items()}
    return {"estimate": est, "ci95": [lo, hi], "per_fold": per_fold, "coverage": cov}


def _fmt(c: dict) -> str:
    folds = " ".join(f"{v:+4.0%}" for v in c["per_fold"].values())
    return f"{c['estimate']:+6.1%} [{c['ci95'][0]:+5.0%},{c['ci95'][1]:+5.0%}] ({folds})"


# --- figure ---------------------------------------------------------------------
def plot_curve(folds: dict, rho: str, subsets: dict[str, list[int]], path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted, grid, surface = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
    series = [("raised threshold", "#2a78d6", "o"), ("Gc", "#eb6834", "s"),
              ("Gcs", "#1baf7a", "D"), ("Gcs@default", "#eda100", "^")]  # fmt: skip
    fig, axes = plt.subplots(1, len(subsets), figsize=(5.2 * len(subsets), 4), facecolor=surface)
    for ax, (title, recs) in zip(np.atleast_1d(axes), subsets.items(), strict=True):
        ax.set_facecolor(surface)
        rows = _get(next(iter(folds.values())), ("targets", rho, "oracle"))
        for name, color, marker in series:
            if name == "raised threshold":
                y = agg([_get(f, ("targets", rho, "oracle", "threshold"))
                         for f in folds.values()], recs)["fvh"]  # fmt: skip
                xs, ys = [1.0], [y]
                ax.axhline(y, color=color, lw=1, ls=(0, (4, 3)), zorder=1)
            else:
                xs, ys = [], []
                for cap in rows[name]:
                    a = agg([_get(f, ("targets", rho, "oracle", name, cap))
                             for f in folds.values()], recs)  # fmt: skip
                    xs.append(a["coverage"])
                    ys.append(a["fvh"])
            ax.plot(xs, ys, color=color, lw=2, marker=marker, ms=8, mec=surface, mew=2,
                    label=name, zorder=3)  # fmt: skip
            ax.annotate(name, (xs[0], ys[0]), xytext=(6, 0), textcoords="offset points",
                        va="center", fontsize=8, color=ink)  # fmt: skip
        ax.axvline(RULE, color=muted, lw=1, zorder=0)
        ax.text(RULE, ax.get_ylim()[1], " coverage rule", color=muted, fontsize=8, va="top")
        ax.set_title(title, color=ink, fontsize=10, loc="left")
        ax.set_xlabel("windows kept (coverage)", color=muted, fontsize=9)
        ax.set_ylabel("false V calls / hour", color=muted, fontsize=9)
        ax.set_xlim(0.77, 1.04)
        ax.grid(axis="y", color=grid, lw=0.6)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color("#c3c2b7")
        ax.tick_params(colors=muted, labelsize=8)
    np.atleast_1d(axes)[0].legend(frameon=False, fontsize=8, loc="center left")
    fig.suptitle(f"Held-out noise, V retention matched at {rho} x Robust default (oracle)",
                 color=ink, fontsize=10, x=0.01, ha="left")  # fmt: skip
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=surface)
    plt.close(fig)


# --- report ---------------------------------------------------------------------
def full_pilot() -> None:
    targets = config.pipeline()["thresholds"]["retention_targets"]
    data = process_all(ds1_copies())
    base, C = base_model(data)
    print(f"Base: C = {C}")
    folds = {}
    for h in config.splits()["noise"]["types"]:
        t = time.perf_counter()
        folds[h] = fold(h, data, C, base, targets)
        print(f"fold held-out {h}: {time.perf_counter() - t:.0f} s")

    recs = folds[next(iter(folds))]["robust"]["records"]
    clean_fv = {r: float(np.mean([f["clean_fv_h"][r] for f in folds.values()])) for r in recs}
    flagged = [r for r in recs if clean_fv[r] > EVAL["clean_error_fv_h"]]
    subsets = {"all records": recs, f"without {', '.join(map(str, flagged))}":
               [r for r in recs if r not in flagged]}  # fmt: skip
    rho = str(targets[0])
    rule = f"{RULE:.2f}"
    summary: dict = {"C": C, "clean_fv_h": clean_fv, "clean_error_records": flagged,
                     "folds": folds, "primary": {}, "secondary": {}}  # fmt: skip

    print("\nRobust false V/h on each record's CLEAN copy (classifier errors without noise):")
    marks = "  ".join(f"{r}: {v:.0f}{'*' if r in flagged else ''}" for r, v in clean_fv.items())
    print(f"   {marks}   (* > {EVAL['clean_error_fv_h']}/h: also reported without)")
    print("Risky (gate label) share of dev windows: "
          + ", ".join(f"{h} {f['risky_frac_dev']:.1%}" for h, f in folds.items()))  # fmt: skip

    # 1. primary
    comps = [
        ("Gcs vs raised threshold", ("threshold",), ("Gcs", rule)),
        ("Gcs@default vs raised threshold", ("threshold",), ("Gcs@default", rule)),
        ("Gc vs raised threshold", ("threshold",), ("Gc", rule)),
        ("Gcs vs Gc (same deferral cap)", ("Gc", rule), ("Gcs", rule)),
    ]
    print(f"\n1. PRIMARY: oracle operating points, retention {rho} x Robust default, deferral "
          f"cap {1 - RULE:.0%}.\n   Reduction in false V/h, 95 % record-bootstrap CI, "
          "(per fold em ma bw)")  # fmt: skip
    print(f"   {'':34s} " + "  ".join(f"{s:38s}" for s in subsets))
    for name, rk, ak in comps:
        cells = {s: compare(folds, ("targets", rho, "oracle", *rk), ("targets", rho, "oracle", *ak),
                            rs) for s, rs in subsets.items()}  # fmt: skip
        summary["primary"][name] = cells
        print(f"   {name:34s} " + "  ".join(f"{_fmt(c):38s}" for c in cells.values()))
    cov = compare(folds, ("targets", rho, "oracle", "threshold"),
                  ("targets", rho, "oracle", "Gcs", rule), recs)["coverage"]  # fmt: skip
    print("   Gcs coverage per fold: " + ", ".join(f"{h} {v:.0%}" for h, v in cov.items()))

    # 2. per record
    print("\n2. Per record (pooled over folds): Gcs vs raised threshold | clean-copy false V/h")
    thr_rec = agg([_get(f, ("targets", rho, "oracle", "threshold")) for f in folds.values()], recs)
    gcs_rec = agg([_get(f, ("targets", rho, "oracle", "Gcs", rule)) for f in folds.values()], recs)
    for i, r in enumerate(recs):
        red = 1 - gcs_rec["fvh_rec"][i] / max(thr_rec["fvh_rec"][i], 1e-9)
        share = thr_rec["fvh_rec"][i] / thr_rec["fvh_rec"].sum()
        print(f"   {r}: {red:+5.0%}   share of threshold-arm false V {share:4.0%}   "
              f"clean copy {clean_fv[r]:6.0f}/h")

    # 3. coverage curve
    print(f"\n3. Coverage curve (oracle, retention {rho}): false V/h | coverage achieved")
    for s, rs in subsets.items():
        thr = agg([_get(f, ("targets", rho, "oracle", "threshold")) for f in folds.values()], rs)
        print(f"   {s}: raised threshold {thr['fvh']:.0f}/h at 100 %")
        print(f"     {'cap':>5}  " + "  ".join(f"{g:>16s}" for g in GATES) + "   Gcs vs Gc")
        for cap in CAPS:
            k = f"{cap:.2f}"
            cells = [agg([_get(f, ("targets", rho, "oracle", g, k)) for f in folds.values()], rs)
                     for g in GATES]  # fmt: skip
            gg = compare(folds, ("targets", rho, "oracle", "Gc", k),
                         ("targets", rho, "oracle", "Gcs", k), rs)  # fmt: skip
            print(f"     {cap:5.0%}  " + "  ".join(f"{c['fvh']:7.0f} | {c['coverage']:4.0%}  "
                                                  for c in cells) + f"  {_fmt(gg)}")  # fmt: skip
            summary["primary"].setdefault("coverage_curve", {}).setdefault(s, {})[k] = {
                **{g: {"fvh": c["fvh"], "coverage": c["coverage"]}
                   for g, c in zip(GATES, cells, strict=True)},
                "raised_threshold_fvh": thr["fvh"], "Gcs_vs_Gc": gg}  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    plot_curve(folds, rho, subsets, OUT / "coverage_curve.png")

    # 4. secondary: dev-set operating points transferred to the held-out noise
    print(f"\n4. SECONDARY: operating points set on the other two noise types (deployment-like), "
          f"cap {1 - RULE:.0%} deferral.\n   Coverage and retention reached on the held-out noise "
          "(! = below the coverage rule):")  # fmt: skip
    for g in ("Gc", "Gcs", "Gcs@default"):
        cells = []
        for h, f in folds.items():
            a = agg([_get(f, ("targets", rho, "dev", g, rule))], recs)
            o = agg([_get(f, ("targets", rho, "oracle", "threshold"))], recs)
            cells.append(f"{h} {a['coverage']:4.0%}{'!' if a['coverage'] < RULE else ' '} "
                         f"ret {a['retention']:.3f} (target {o['retention']:.3f})")  # fmt: skip
        print(f"   {g:12s} " + "   ".join(cells))
    for name, rk, ak in comps:
        cells = {s: compare(folds, ("targets", rho, "dev", *rk), ("targets", rho, "dev", *ak), rs)
                 for s, rs in subsets.items()}  # fmt: skip
        summary["secondary"][name] = cells
        print(f"   {name:34s} " + "  ".join(f"{_fmt(c):38s}" for c in cells.values()))

    # 5. other retention targets
    print("\n5. Other retention targets (oracle, Gcs vs raised threshold):")
    for other in targets[1:]:
        cells = {s: compare(folds, ("targets", str(other), "oracle", "threshold"),
                            ("targets", str(other), "oracle", "Gcs", rule), rs)
                 for s, rs in subsets.items()}  # fmt: skip
        print(f"   {other}: " + "   ".join(f"{s}: {_fmt(c)}" for s, c in cells.items()))

    print("\nNote: in oracle mode the gated arms tune two settings (SVM threshold, gate cut-off)"
          " on the held-out data,\nthe raised-threshold arm one; @default rows tune only the"
          " cut-off.")  # fmt: skip
    print("\nRobust (default) by SNR on held-out noise: false V/h | risky window fraction")
    for h, f in folds.items():
        print(f"   {h}: " + "  ".join(
            f"{k}: {v['robust_fv_h']:.0f}|{v['risky_frac']:.2f}" for k, v in f["by_snr"].items()))
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
    print(f"\nwrote {OUT / 'summary.json'} and {OUT / 'coverage_curve.png'}")


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
        fvh = s.false_v[:, d].sum() / (len(s) * WIN_H)
        print(f"record {record} {cp:5s}: {fvh:6.1f} false V/h, "
              f"V retention {retention(s, d):.3f}, {s.risky.mean():.0%} risky windows")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", type=int, help="Step 2: one DS1-cal record with Base")
    ap.add_argument("--noise", default="em")
    a = ap.parse_args()
    one_record(a.record, a.noise) if a.record else full_pilot()


if __name__ == "__main__":
    main()
