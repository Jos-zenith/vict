"""Phase 0 final step: the single DS2 run, from a freeze tag, and the claim rule.

  python scripts/run_ds2.py --dry-run   # same code with DS1-cal standing in for DS2
  python scripts/run_ds2.py             # the real run (HEAD must be a clean freeze-* tag)

Models (DS1 only):
  Base     SVM on clean DS1-train detections, C by record-grouped CV
  Robust   SVM on DS1-train clean + noisy copies (all noise types, train blocks), same C
  Gc, Gcs  gates on DS1-cal noisy copies (cal blocks); risky labels from Robust
Evaluation: DS2 records (202 only in the sensitivity check), each clean and mixed with
every noise type at every cycle offset using the noise test blocks; arms are scored on
the noisy copies, with one operating point per arm for the whole set.

Operating points (fixed before the freeze; neither looks at false V calls):
  target            rho x Robust's default V retention (rho = first retention target)
  raised threshold  highest SVM threshold with retention >= target
  Gcs, Gc           SVM at its default threshold; defer the riskiest windows while
                    retention >= target, at most 1 - min_effective_coverage of the
                    windows of each noise type (one cut-off for all windows)
Claim rule (all DS2 records; r = relative reduction in false V/h of Gcs vs the
raised threshold, with its 95 % record-bootstrap CI):
  GATE WINS       r >= min_meaningful_effect, CI lower bound > 0, and Gcs keeps
                  >= min_effective_coverage of the windows for every noise type
  THRESHOLD WINS  CI upper bound < 0
  INCONCLUSIVE    otherwise
Reported but not deciding: the same without clean-error records (clean copy above
clean_error_fv_h false V/h under Robust), Gcs vs Gc, per noise type, with 202, and the
other retention targets.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from functools import partial

import numpy as np

from vgate import config
from vgate.evaluation.operating import arm_rows, defer_cutoff, highest_threshold, retention
from vgate.evaluation.stats import bootstrap_ci
from vgate.models.classifiers import make_svm, select_C
from vgate.models.gates import make_gate
from vgate.pipeline import Copy, ds1_copies, ds2_copies, process, to_windows, training_data
from vgate.windows import WindowTable

WIN_H = config.pipeline()["window_s"] / 3600
EVAL = config.pipeline()["evaluation"]


# --- freeze guard ---------------------------------------------------------------
def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=config.ROOT, capture_output=True, text=True,
                          check=False).stdout.strip()  # fmt: skip


def freeze_tag() -> tuple[str, str]:
    """(tag, commit) of HEAD; exits unless HEAD is a freeze-* tag with no local changes."""
    tag = _git("describe", "--exact-match", "--tags", "HEAD")
    if not tag.startswith("freeze-"):
        sys.exit("DS2 runs only from a freeze-* tag: git checkout <tag> first.")
    if _git("status", "--porcelain", "--untracked-files=no"):
        sys.exit("Tracked files differ from the freeze tag; DS2 must run on the frozen code.")
    return tag, _git("rev-parse", "HEAD")


# --- models -----------------------------------------------------------------------
def process_all(copies: list[Copy], allow_test: bool = False) -> dict[Copy, dict]:
    t = time.perf_counter()
    with ProcessPoolExecutor() as ex:
        out = list(ex.map(partial(process, allow_test=allow_test), copies))
    print(f"processed {len(copies)} copies in {time.perf_counter() - t:.0f} s")
    return dict(zip(copies, out, strict=True))


def _xy(copies: list[Copy], data: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    parts = [training_data(data[c]) for c in copies]
    groups = [np.full(len(p[1]), c.record) for c, p in zip(copies, parts, strict=True)]
    return (np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts]),
            np.concatenate(groups))  # fmt: skip


def tables(model, copies: list[Copy], data: dict) -> WindowTable:
    out = []
    for r in sorted({c.record for c in copies}):
        mine = [c for c in copies if c.record == r]
        cc = next(c for c in mine if c.copy == "clean")
        dec = {c: model.decision_function(data[c]["features"]) for c in mine}
        clean = to_windows(cc, data[cc], dec[cc])
        out += [clean] + [to_windows(c, data[c], dec[c], clean) for c in mine if c.copy == "noisy"]
    return WindowTable.concat(out)


def train(dev: dict) -> dict:
    train_c = [c for c in dev if c.split == "train"]
    cal_c = [c for c in dev if c.split == "cal"]
    X, y, g = _xy([c for c in train_c if c.copy == "clean"], dev)
    C = select_C(X, y, g)
    base = make_svm(C).fit(X, y)
    X, y, _ = _xy(train_c, dev)
    robust = make_svm(C).fit(X, y)
    cal = tables(robust, cal_c, dev)
    cal = cal.subset(cal.copy == "noisy")
    gates = {name: make_gate().fit(cal.gate_features(sqi), cal.risky)
             for name, sqi in (("Gc", False), ("Gcs", True))}  # fmt: skip
    print(f"C = {C}; gate training: {len(cal)} DS1-cal windows, {cal.risky.mean():.1%} risky")
    return {"C": C, "base": base, "robust": robust, "gates": gates}


def save_models(m: dict, path) -> None:
    def lin(p):
        s, last = p[0], p[-1]
        return {"mean": s.mean_, "scale": s.scale_, "coef": last.coef_.ravel(),
                "intercept": np.atleast_1d(last.intercept_)}  # fmt: skip

    arrays = {f"{name}_{k}": v for name in ("base", "robust") for k, v in lin(m[name]).items()}
    arrays |= {f"{g}_{k}": v for g, p in m["gates"].items() for k, v in lin(p).items()}
    np.savez(path, C=m["C"], **arrays)


# --- evaluation -------------------------------------------------------------------
def evaluate(t: WindowTable, gates: dict, rho: float) -> dict:
    """Arms on the noisy rows of ``t`` at retention target rho x Robust default."""
    noisy = t.subset(t.copy == "noisy")
    d = noisy.default_index
    all_kept = np.ones(len(noisy), bool)
    target = rho * retention(noisy, d)
    k = highest_threshold(noisy, target)
    arms = {"robust": (d, all_kept), "threshold": (k, all_kept)}
    for name, sqi in (("Gc", False), ("Gcs", True)):
        risk = gates[name].predict_proba(noisy.gate_features(sqi))[:, 1]
        cut = defer_cutoff(noisy, risk, target, d, EVAL["min_effective_coverage"],
                           groups=noisy.noise_type)
        arms[name] = (d, risk < cut)

    out: dict = {"target": target}
    for name, (kk, keep) in arms.items():
        out[name] = arm_rows(noisy, kk, keep, WIN_H)
    for g in ("Gc", "Gcs"):
        keep = arms[g][1]
        out[g]["coverage_by_noise"] = {str(n): float(keep[noisy.noise_type == n].mean())
                                       for n in np.unique(noisy.noise_type)}  # fmt: skip
    out["by_noise"] = {}
    for n in np.unique(noisy.noise_type):
        sub = noisy.noise_type == n
        out["by_noise"][str(n)] = {name: arm_rows(noisy.subset(sub), kk, keep[sub], WIN_H)
                                   for name, (kk, keep) in arms.items()}  # fmt: skip
    return out


def summarise(rows: dict, recs: list[int]) -> dict:
    idx = [rows["records"].index(r) for r in recs]
    names = ("false_v", "called_v", "true_v", "kept", "windows")
    get = {n: np.asarray(rows[n])[idx] for n in names}
    hours = get["windows"] * WIN_H
    return {"fvh_rec": get["false_v"] / hours, "fvh": get["false_v"].sum() / hours.sum(),
            "retention": get["called_v"].sum() / max(get["true_v"].sum(), 1),
            "coverage": get["kept"].sum() / get["windows"].sum()}  # fmt: skip


def compare(ref: dict, arm: dict, recs: list[int]) -> dict:
    a, b = summarise(ref, recs), summarise(arm, recs)
    est, lo, hi = bootstrap_ci(a["fvh_rec"], b["fvh_rec"], n=EVAL["bootstrap_resamples"],
                               seed=EVAL["seed"])  # fmt: skip
    return {"estimate": est, "ci95": [lo, hi], "ref_fvh": a["fvh"], "arm_fvh": b["fvh"],
            "ref_retention": a["retention"], "arm_retention": b["retention"],
            "arm_coverage": b["coverage"]}  # fmt: skip


def verdict(c: dict, coverage_by_noise: dict) -> str:
    lo, hi = c["ci95"]
    cov_ok = all(v >= EVAL["min_effective_coverage"] for v in coverage_by_noise.values())
    if c["estimate"] >= EVAL["min_meaningful_effect"] and lo > 0 and cov_ok:
        return "GATE WINS"
    if hi < 0:
        return "THRESHOLD WINS"
    return "INCONCLUSIVE"


def _line(name: str, c: dict) -> str:
    return (f"| {name} | {c['estimate']:+.1%} | [{c['ci95'][0]:+.1%}, {c['ci95'][1]:+.1%}] | "
            f"{c['ref_fvh']:.1f} -> {c['arm_fvh']:.1f} | {c['ref_retention']:.3f} -> "
            f"{c['arm_retention']:.3f} | {c['arm_coverage']:.1%} |")  # fmt: skip


def report(res: dict, recs: list[int], clean_fv: dict, flagged: list[int], header: str) -> str:
    rho = str(config.pipeline()["thresholds"]["retention_targets"][0])
    main = res[rho]
    primary = compare(main["threshold"], main["Gcs"], recs)
    cov = main["Gcs"]["coverage_by_noise"]
    v = verdict(primary, cov)
    rest = [r for r in recs if r not in flagged]
    head = ("| comparison | reduction | 95 % CI | false V/h | V retention | coverage |\n"
            "|---|---|---|---|---|---|")
    lines = [
        header, "", f"## Verdict: **{v}**", "",
        f"Claim rule: Gcs vs raised threshold on all {len(recs)} records, retention "
        f"{rho} x Robust default ({main['target']:.3f}); gate wins if the reduction >= "
        f"{EVAL['min_meaningful_effect']:.0%}, the CI lower bound > 0 and Gcs coverage >= "
        f"{EVAL['min_effective_coverage']:.0%} for every noise type "
        f"({', '.join(f'{k} {x:.1%}' for k, x in cov.items())}).", "",
        "## Results (retention target " + rho + ")", "", head,
        _line("**Gcs vs raised threshold (deciding)**", primary),
        _line("Gc vs raised threshold", compare(main["threshold"], main["Gc"], recs)),
        _line("Gcs vs Gc", compare(main["Gc"], main["Gcs"], recs)),
        _line("Robust (default) -> raised threshold", compare(main["robust"], main["threshold"],
                                                             recs)),  # fmt: skip
        "", f"Without clean-error records ({', '.join(map(str, flagged)) or 'none'}; clean copy "
        f"> {EVAL['clean_error_fv_h']} false V/h):", "", head,
    ]
    if rest and flagged:
        lines += [_line("Gcs vs raised threshold", compare(main["threshold"], main["Gcs"], rest)),
                  _line("Gcs vs Gc", compare(main["Gc"], main["Gcs"], rest))]  # fmt: skip
    lines += ["", "Per noise type (shared operating point):", "", head]
    for n, b in main["by_noise"].items():
        c = compare(b["threshold"], b["Gcs"], recs)
        lines.append(_line(f"{n}: Gcs vs raised threshold", c))
    lines += ["", "Other retention targets:", "", head]
    for other, r in res.items():
        if other != rho and other != "with_202":
            lines.append(_line(f"{other}: Gcs vs raised threshold",
                               compare(r["threshold"], r["Gcs"], recs)))  # fmt: skip
    if "with_202" in res:
        w = res["with_202"]
        lines += ["", "Sensitivity: with record 202:", "", head,
                  _line("Gcs vs raised threshold", compare(w["threshold"], w["Gcs"],
                                                           w["threshold"]["records"]))]  # fmt: skip
    lines += ["", "Robust false V/h on each record's clean copy: "
              + ", ".join(f"{r} {x:.0f}" for r, x in clean_fv.items())]  # fmt: skip
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="run everything with DS1-cal standing in for DS2; never touches DS2")
    a = ap.parse_args()
    targets = config.pipeline()["thresholds"]["retention_targets"]

    if a.dry_run:
        tag, commit = "dry-run", _git("rev-parse", "HEAD")
        out_dir = config.RESULTS_DIR / "ds2" / "dry-run"
    else:
        tag, commit = freeze_tag()
        out_dir = config.RESULTS_DIR / "ds2" / tag
        if (out_dir / "verdict.md").exists():
            sys.exit(f"DS2 already ran for {tag}: {out_dir / 'verdict.md'}. It runs once.")
    out_dir.mkdir(parents=True, exist_ok=True)

    dev = process_all(ds1_copies())
    models = train(dev)
    save_models(models, out_dir / "models.npz")
    if a.dry_run:
        ev_copies = [c for c in dev if c.split == "cal"]
        ev_data, ev_sens = dev, None
    else:
        ev_copies = ds2_copies()
        ev_data = process_all(ds2_copies(include_202=True), allow_test=True)
        ev_sens = ds2_copies(include_202=True)

    t = tables(models["robust"], ev_copies, ev_data)
    t.save(out_dir / "windows.npz")
    recs = sorted({c.record for c in ev_copies})
    clean = t.subset(t.copy == "clean")
    d = clean.default_index
    clean_fv = {r: float(clean.false_v[clean.record == r, d].sum()
                         / ((clean.record == r).sum() * WIN_H)) for r in recs}  # fmt: skip
    flagged = [r for r in recs if clean_fv[r] > EVAL["clean_error_fv_h"]]

    res = {str(rho): evaluate(t, models["gates"], rho) for rho in targets}
    if ev_sens:
        res["with_202"] = evaluate(tables(models["robust"], ev_sens, ev_data), models["gates"],
                                   targets[0])  # fmt: skip

    what = "DRY RUN on DS1-cal (gates trained on these records; plumbing only)" if a.dry_run \
        else f"DS2, frozen tag {tag}"  # fmt: skip
    text = report(res, recs, clean_fv, flagged,
                  f"# vgate DS2 verdict - {what}\n\ncommit `{commit}`, {time.strftime('%Y-%m-%d')}")
    (out_dir / "verdict.md").write_text(text, encoding="utf-8")
    (out_dir / "verdict.json").write_text(json.dumps(
        {"tag": tag, "commit": commit, "clean_fv_h": clean_fv, "clean_error_records": flagged,
         "results": res}, indent=1, default=float))  # fmt: skip
    print(text)
    print(f"wrote {out_dir / 'verdict.md'}")


if __name__ == "__main__":
    main()
