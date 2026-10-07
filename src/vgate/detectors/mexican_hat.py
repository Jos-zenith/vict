"""Mexican-hat (Ricker) detector, used only for qSQI.

Spec: causal FIR, sigma = 25 ms, threshold at 40 % of the running 2 s maximum.
The FIR spans +/-4 sigma (zero-mean) and delays the output by 4 sigma; detections
are shifted back by that delay. Peaks of |output| above the threshold, at most one
per refractory period (the larger wins).
"""

from __future__ import annotations

import numpy as np
from scipy import signal
from scipy.ndimage import maximum_filter1d

from vgate import config


def kernel(fs: int = 360) -> np.ndarray:
    sigma = config.pipeline()["mexican_hat"]["sigma_ms"] * fs / 1000
    half = round(4 * sigma)
    t = np.arange(-half, half + 1) / sigma
    h = (1 - t**2) * np.exp(-(t**2) / 2)
    return h - h.mean()


def detect(x: np.ndarray, fs: int = 360) -> np.ndarray:
    cfg = config.pipeline()["mexican_hat"]
    h = kernel(fs)
    delay = len(h) // 2
    x = np.asarray(x, float)
    a = np.abs(signal.lfilter(h, 1.0, x - x[0]))
    a[: len(h)] = 0.0  # filter start-up
    n = round(cfg["running_max_s"] * fs)
    run_max = maximum_filter1d(a, n, origin=(n - 1) // 2)  # max over the past n samples
    thr = cfg["threshold_frac"] * run_max
    peaks = np.flatnonzero((a[1:-1] > a[:-2]) & (a[1:-1] >= a[2:]) & (a[1:-1] > thr[1:-1])) + 1
    refractory = round(config.pipeline()["pan_tompkins"]["refractory_ms"] * fs / 1000)
    kept: list[int] = []
    for p in peaks:
        if kept and p - kept[-1] < refractory:
            if a[p] > a[kept[-1]]:
                kept[-1] = p
        else:
            kept.append(int(p))
    return np.clip(np.asarray(kept, dtype=int) - delay, 0, None)
