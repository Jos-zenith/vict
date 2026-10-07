"""Signal-quality indices (Zhao & Zhang 2018): qSQI, pSQI, kSQI, basSQI.

Computed per 10 s window with only its mean removed, then log-transformed.
  qSQI    matched / (n_PT + n_MH - matched), detections matched within the scoring
          tolerance (0 when neither detector fires)
  pSQI    power in 5-15 Hz / power in 5-40 Hz (QRS energy share)
  kSQI    kurtosis (Pearson, normal = 3)
  basSQI  1 - power in 0-1 Hz / power in 0-40 Hz (baseline wander)
Spectra are Welch PSDs with 4 s Hann segments.
Owner: Shapari.
"""

from __future__ import annotations

import numpy as np
from scipy import signal, stats

from vgate import config
from vgate.evaluation.matching import match

LOG_FLOOR = 1e-3  # log(0) guard: keeps an empty window at log 1e-3, not -27


def qsqi(r_pt: np.ndarray, r_mh: np.ndarray, fs: int = 360) -> float:
    """Agreement between Pan-Tompkins and Mexican-hat detections."""
    tol = round(config.pipeline()["scoring"]["match_tolerance_ms"] * fs / 1000)
    _, r2d = match(np.asarray(r_mh, int), np.asarray(r_pt, int), tol)
    m = int((r2d >= 0).sum())
    total = len(r_pt) + len(r_mh) - m
    return m / total if total else 0.0


def _band_power(f: np.ndarray, p: np.ndarray, lo: float, hi: float) -> float:
    return float(p[(f >= lo) & (f <= hi)].sum())


def _psd(x: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    return signal.welch(x, fs=fs, nperseg=min(len(x), 4 * fs))


def psqi(x: np.ndarray, fs: int = 360) -> float:
    f, p = _psd(x, fs)
    den = _band_power(f, p, 5, 40)
    return _band_power(f, p, 5, 15) / den if den > 0 else 0.0


def ksqi(x: np.ndarray) -> float:
    return float(stats.kurtosis(x, fisher=False)) if np.ptp(x) > 0 else 0.0


def bassqi(x: np.ndarray, fs: int = 360) -> float:
    f, p = _psd(x, fs)
    den = _band_power(f, p, 0, 40)
    return 1 - _band_power(f, p, 0, 1) / den if den > 0 else 0.0


def window_sqis(x: np.ndarray, r_pt: np.ndarray, r_mh: np.ndarray, fs: int = 360) -> np.ndarray:
    """Log of the four SQIs for one window, in the order q, p, k, bas."""
    x = x - x.mean()
    raw = np.array([qsqi(r_pt, r_mh, fs), psqi(x, fs), ksqi(x), bassqi(x, fs)])
    return np.log(np.clip(raw, LOG_FLOOR, None))
