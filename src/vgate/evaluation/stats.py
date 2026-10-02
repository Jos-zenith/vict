"""Record-level bootstrap for the pooled relative reduction in false V calls/hour."""

from __future__ import annotations

import numpy as np


def relative_reduction(fv_ref: np.ndarray, fv_arm: np.ndarray) -> float:
    """Total over total: 1 - sum(arm) / sum(reference)."""
    return 1.0 - np.sum(fv_arm) / np.sum(fv_ref)


def bootstrap_ci(
    fv_ref: np.ndarray, fv_arm: np.ndarray, n: int = 10_000, seed: int = 0, alpha: float = 0.05
) -> tuple[float, float, float]:
    """Point estimate and percentile CI, resampling records with replacement.

    fv_ref, fv_arm: false V calls per hour per record, in the same record order.
    """
    fv_ref, fv_arm = np.asarray(fv_ref, float), np.asarray(fv_arm, float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(fv_ref), size=(n, len(fv_ref)))
    ref, arm = fv_ref[idx].sum(1), fv_arm[idx].sum(1)
    ok = ref > 0
    boot = 1.0 - arm[ok] / ref[ok]
    lo, hi = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return relative_reduction(fv_ref, fv_arm), float(lo), float(hi)
