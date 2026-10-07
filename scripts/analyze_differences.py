"""Tag every noisy-vs-clean difference by cause and place (post-hoc, after DS2).

  python scripts/analyze_differences.py

Uses the frozen Robust model as saved by the freeze-v1 DS2 run
(results/ds2/freeze-v1/models.npz), at its default threshold, on the DS1-cal and DS2
noisy copies. Each noisy copy is compared beat by beat with its own clean copy:

  false V calls on the noisy copy
    spurious detection   detection matching no reference beat, called V, with no
                         such call within the match tolerance on the clean copy
    beat reclassified    reference N/S/F beat called V, not called V on clean
    same as clean        the clean copy makes the same false call (not noise)
  true V beats lost on the noisy copy (called V on clean)
    missed detection     no detection matched the beat
    reclassified         detected but not called V
Place: noise type and the SNR of the segment holding the beat ("clean segment" for
windows between noisy segments). Only scored windows count. Writes
docs/paired_differences.md.
"""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from functools import partial

import numpy as np

from vgate import config
from vgate.evaluation.matching import match
from vgate.pipeline import Copy, ds1_copies, ds2_copies, process

MODELS = config.RESULTS_DIR / "ds2" / "freeze-v1" / "models.npz"
OUT = config.ROOT / "docs" / "paired_differences.md"
FALSE_CAUSES = ("spurious detection", "beat reclassified", "same as clean")
LOST_CAUSES = ("missed detection", "reclassified")


def robust_decision(features: np.ndarray, m) -> np.ndarray:
    return ((features - m["robust_mean"]) / m["robust_scale"]) @ m["robust_coef"] + m[
        "robust_intercept"
    ][0]


def _scored(samples: np.ndarray, starts: np.ndarray, win: int) -> tuple[np.ndarray, np.ndarray]:
    w = np.clip(np.searchsorted(starts, samples, side="right") - 1, 0, None)
    ok = (samples >= starts[0]) & (samples < starts[w] + win)
    return w, ok


def tag_copy(pair: tuple[Copy, Copy], m) -> dict:
    clean_c, noisy_c = pair
    allow = noisy_c.split == "test"
    cd, nd = process(clean_c, allow_test=allow), process(noisy_c, allow_test=allow)
    fs = 360
    tol = round(config.pipeline()["scoring"]["match_tolerance_ms"] * fs / 1000)
    win = config.pipeline()["window_s"] * fs
    ref, aami = nd["ref_sample"], nd["ref_aami"]
    starts, snr = nd["starts"], nd["snr_db"]

    out = {}
    called, d2r, r2d = {}, {}, {}
    for k, d in (("c", cd), ("n", nd)):
        called[k] = robust_decision(d["features"], m) > 0
        d2r[k], r2d[k] = match(d["det"], ref, tol)
    ref_called = {k: (r2d[k] >= 0) & called[k][np.maximum(r2d[k], 0)] for k in ("c", "n")}

    def place(sample: int) -> str | None:
        w, ok = _scored(np.array([sample]), starts, win)
        if not ok[0]:
            return None
        s = snr[w[0]]
        return "clean segment" if np.isnan(s) else f"{s:g} dB"

    def add(cause: str, sample: int) -> None:
        p = place(int(sample))
        if p is not None:
            out[(p, cause)] = out.get((p, cause), 0) + 1

    # false V calls on the noisy copy
    clean_spurious = cd["det"][called["c"] & (d2r["c"] < 0)]
    for i in np.flatnonzero(called["n"]):
        j = d2r["n"][i]
        if j < 0:
            near = np.abs(clean_spurious - nd["det"][i]) <= tol
            add("same as clean" if near.any() else "spurious detection", nd["det"][i])
        elif aami[j] in ("N", "S", "F"):
            add("same as clean" if ref_called["c"][j] else "beat reclassified", ref[j])
    # true V beats lost to noise
    for j in np.flatnonzero((aami == "V") & ref_called["c"] & ~ref_called["n"]):
        add("missed detection" if r2d["n"][j] < 0 else "reclassified", ref[j])
    # hours per place
    for i in range(len(starts)):
        p = "clean segment" if np.isnan(snr[i]) else f"{snr[i]:g} dB"
        out[(p, "_hours")] = out.get((p, "_hours"), 0) + win / fs / 3600
    return {"split": noisy_c.split, "noise": noisy_c.noise_type, "counts": out}


def table(rows: list[dict], split: str, noise: str | None) -> list[str]:
    tot: dict = defaultdict(float)
    for r in rows:
        if r["split"] == split and (noise is None or r["noise"] == noise):
            for k, v in r["counts"].items():
                tot[k] += v
    places = sorted({p for p, _ in tot}, key=lambda p: (p == "clean segment", -float(
        p.split()[0]) if p != "clean segment" else 0))  # fmt: skip
    head = ["place", "hours"] + [f"false V: {c}" for c in FALSE_CAUSES] + [
        f"V lost: {c}" for c in LOST_CAUSES]  # fmt: skip
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for p in places + ["all"]:
        keys = places if p == "all" else [p]
        h = sum(tot[(q, "_hours")] for q in keys)
        cells = [f"{sum(tot[(q, c)] for q in keys) / h:.1f}" for c in FALSE_CAUSES + LOST_CAUSES]
        lines.append(f"| {p} | {h:.1f} | " + " | ".join(cells) + " |")
    return lines


def main() -> None:
    m = dict(np.load(MODELS))
    pairs = []
    for copies in (ds1_copies(), ds2_copies()):
        clean = {c.record: c for c in copies if c.copy == "clean"}
        pairs += [(clean[c.record], c) for c in copies if c.copy == "noisy" and c.split != "train"]
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(partial(tag_copy, m=m), pairs))

    doc = [
        "# Paired noisy-vs-clean differences by cause and place",
        "",
        "Post-hoc analysis after the freeze-v1 DS2 run (`scripts/analyze_differences.py`);",
        "it does not affect the verdict. Frozen Robust model at its default threshold, no",
        "gate. Values are events per hour of scored windows at that place; causes are",
        "defined in the script docstring.",
    ]
    names = {"cal": "DS1-cal", "test": "DS2"}
    for split in ("cal", "test"):
        for noise in (None, *config.splits()["noise"]["types"]):
            doc += ["", f"## {names[split]}, {'all noise types' if noise is None else noise}", ""]
            doc += table(rows, split, noise)
    OUT.write_text("\n".join(doc) + "\n", encoding="utf-8")
    print("\n".join(doc))


if __name__ == "__main__":
    main()
