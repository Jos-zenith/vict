"""The frozen v1.0 chain end to end, offline: the reference the C core is checked against.

raw (mV, 360 Hz) -> Pan-Tompkins (detect_with_widths) -> classifier band-pass ->
beat_features -> design.decision -> design.window_states. Nothing here changes the
design; it only strings the frozen pieces together the way scripts/check_c_core.py
and the C golden vectors (scripts/export_c_vectors.py) use them.
"""

from __future__ import annotations

import numpy as np

from vgate import design, windows
from vgate.detectors import pan_tompkins
from vgate.dsp.filters import bandpass
from vgate.features import beat_features


def run(raw: np.ndarray, fs: int = 360) -> dict:
    """R peaks, QRS widths, features, decision values and window states of one record."""
    raw = np.asarray(raw, float)
    det, width = pan_tompkins.detect_with_widths(raw, fs)
    x = bandpass(raw).astype(float)
    feats = beat_features(x, det, fs, width)
    dec = design.decision(feats) if len(det) else np.zeros(0)
    starts = windows.window_starts(len(raw), fs)
    return {
        "det": det,
        "width": width,
        "features": feats,
        "decision": dec,
        "starts": starts,
        "states": design.window_states(det, feats, starts, fs),
    }
