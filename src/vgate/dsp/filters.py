"""Classifier filter: causal 4th-order Butterworth band-pass, float32 SOS."""

from __future__ import annotations

import numpy as np
from scipy import signal

from vgate import config


def design_bandpass(fs: int | None = None) -> np.ndarray:
    """SOS coefficients (float32) for the 0.5-40 Hz classifier band-pass.

    ``order`` in the config is the overall filter order, so the band-pass
    prototype order passed to SciPy is order // 2.
    """
    cfg = config.pipeline()
    fs = fs or cfg["fs"]
    f = cfg["filter"]
    sos = signal.butter(f["order"] // 2, f["band_hz"], btype="bandpass", fs=fs, output="sos")
    return sos.astype(f["dtype"])


def bandpass(x: np.ndarray, sos: np.ndarray | None = None) -> np.ndarray:
    """Causal filtering, initialised to the steady state for the first sample."""
    sos = design_bandpass() if sos is None else sos
    x = np.asarray(x, dtype=sos.dtype)
    zi = signal.sosfilt_zi(sos).astype(sos.dtype) * x[0]
    y, _ = signal.sosfilt(sos, x, zi=zi)
    return y.astype(sos.dtype)
