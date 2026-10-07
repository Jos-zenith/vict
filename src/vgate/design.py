"""The v1.0 product design: threshold-only (docs/phase1_design_decision.md).

Frozen as git tag v1.0-threshold. Per beat, the Robust SVM (weights in
models/v1.0_robust.json, trained at freeze-v1) calls V when its decision value is
above the default threshold, 0. Per 10 s window the output is one of:

  "insufficient"  fewer than [windowing] min_beats beats detected (no V calls)
  "V suspected"   at least one beat called V
  "no V"          otherwise

There is no signal-quality deferral: the qSQI rule and the Gcs gate both failed
their pre-registered transfer tests. Nothing here may be tuned on external or
pilot data; a change is a new frozen version.
"""

from __future__ import annotations

import json
from functools import cache

import numpy as np

from vgate import config
from vgate.features import FEATURE_NAMES

WEIGHTS = config.ROOT / "models" / "v1.0_robust.json"
THRESHOLD = 0.0
STATES = ("insufficient", "V suspected", "no V")


@cache
def robust_weights() -> dict:
    w = json.loads(WEIGHTS.read_text(encoding="utf-8"))
    if tuple(w["features"]) != FEATURE_NAMES:
        raise ValueError("models/v1.0_robust.json was trained on a different feature list")
    return w


def decision(features: np.ndarray) -> np.ndarray:
    """Robust's decision value per beat (features: beat_features output)."""
    w = robust_weights()
    z = (np.asarray(features, float) - np.asarray(w["mean"])) / np.asarray(w["scale"])
    return z @ np.asarray(w["coef"]) + w["intercept"]


def window_states(
    det: np.ndarray, features: np.ndarray, starts: np.ndarray, fs: int = 360
) -> list[str]:
    """v1.0 output for each window starting at ``starts`` (samples)."""
    win = config.pipeline()["window_s"] * fs
    min_beats = config.pipeline()["windowing"]["min_beats"]
    det = np.asarray(det, int)
    is_v = decision(features) > THRESHOLD if len(det) else np.zeros(0, bool)
    out = []
    for s in starts:
        inside = (det >= s) & (det < s + win)
        if inside.sum() < min_beats:
            out.append("insufficient")
        else:
            out.append("V suspected" if is_v[inside].any() else "no V")
    return out
