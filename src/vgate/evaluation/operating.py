"""Operating points on a WindowTable, and per-record counts for each arm.

V retention = true V beats called V in kept windows / all true V beats. A gate
defers a window (no V calls in it) when its risk >= the cut-off.

DS2 rules (fixed before the run; neither looks at false V calls):
  highest_threshold  raised-threshold arm: the highest SVM threshold whose
                     retention is still >= target
  defer_cutoff       gated arm at a fixed SVM threshold: defer the riskiest windows,
                     as many as retention >= target allows, at most 1 - cap of them
                     (optionally within every group, e.g. noise type)
The pilot's pair search (``operating_point``) additionally picks the SVM threshold
with the fewest false V calls.
"""

from __future__ import annotations

import numpy as np

from vgate.windows import WindowTable


def retention(t: WindowTable, k: int, keep: np.ndarray | None = None) -> float:
    keep = np.ones(len(t), bool) if keep is None else keep
    return float(((t.n_true_v - t.lost_v[:, k]) * keep).sum() / max(t.n_true_v.sum(), 1))


def highest_threshold(t: WindowTable, target: float) -> int:
    """Highest threshold index with retention >= target (the default if none is)."""
    total = max(t.n_true_v.sum(), 1)
    ret = (t.n_true_v[:, None] - t.lost_v).sum(0) / total
    ok = np.flatnonzero(ret >= target)
    return int(ok.max()) if len(ok) else t.default_index


def defer_cutoff(
    t: WindowTable,
    risk: np.ndarray,
    target: float,
    k: int,
    cap: float,
    groups: np.ndarray | None = None,
) -> float:
    """Gate cut-off at SVM threshold k (see module docstring); inf = defer nothing.

    groups: if given (e.g. noise type per window), coverage >= cap must hold within
    every group, not only overall; the cut-off is still one value for all windows.
    """
    total = max(t.n_true_v.sum(), 1)
    called = (t.n_true_v - t.lost_v[:, k]).astype(float)
    order = np.argsort(-risk, kind="stable")
    ret = (called.sum() - np.concatenate([[0.0], np.cumsum(called[order])])) / total
    ok = ret >= target  # ok[m]: deferring the m riskiest windows keeps retention
    groups = np.zeros(len(risk), int) if groups is None else np.asarray(groups)
    for g in np.unique(groups):
        in_g = groups[order] == g
        deferred = np.concatenate([[0], np.cumsum(in_g)])
        ok &= deferred <= (1 - cap) * in_g.sum() + 1e-9
    m = int(np.argmin(ok)) - 1 if not ok.all() else len(ok) - 1  # ok is a prefix
    return float(risk[order[m - 1]]) if m > 0 else np.inf


def operating_point(
    t: WindowTable, risk: np.ndarray | None, target: float, ks: np.ndarray, cap: float
) -> tuple[int, float]:
    """(SVM threshold index, gate cut-off) with the fewest false V at retention >= target.

    Windows with risk >= cut-off are deferred (no V calls). risk None: no gate.
    Searches every threshold in ``ks``; for each, defers the riskiest windows first,
    as many as retention allows but at most 1 - cap of the windows.
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
    m = (ret >= target).sum(0) - 1  # deferrals allowed; -1 if even none reach target
    m = np.minimum(m, int(round((1 - cap) * len(risk), 9)))
    best = np.where(m >= 0, fv_left[np.maximum(m, 0), np.arange(len(ks))], np.inf)
    if not np.isfinite(best).any():
        return t.default_index, np.inf
    j = int(np.argmin(best))
    cut = float(risk[order[m[j] - 1]]) if m[j] > 0 else np.inf
    return int(ks[j]), cut


def arm_rows(t: WindowTable, k: int, keep: np.ndarray, win_h: float) -> dict:
    """Per-record counts at SVM threshold k with windows ``keep``, so any record
    subset can be re-aggregated. win_h: window length in hours."""
    recs = np.unique(t.record)
    per = {
        "false_v": t.false_v[:, k] * keep,
        "called_v": (t.n_true_v - t.lost_v[:, k]) * keep,
        "true_v": t.n_true_v,
        "kept": keep.astype(int),
        "windows": np.ones(len(t), int),
    }
    out = {name: [int(v[t.record == r].sum()) for r in recs] for name, v in per.items()}
    return {"records": recs.tolist(), **out, "hours_per_window": win_h,
            "thr": float(t.thresholds[k])}  # fmt: skip
