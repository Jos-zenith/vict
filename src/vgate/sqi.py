"""Signal-quality indices (Zhao & Zhang 2018): qSQI, pSQI, kSQI, basSQI.

Computed per 10 s window with only its mean removed, then log-transformed.
Owner: Shapari.
"""

from __future__ import annotations

import numpy as np


def qsqi(r_pt: np.ndarray, r_mh: np.ndarray, fs: int = 360) -> float:
    """Agreement between Pan-Tompkins and Mexican-hat detections."""
    raise NotImplementedError


def psqi(x: np.ndarray, fs: int = 360) -> float:
    raise NotImplementedError


def ksqi(x: np.ndarray) -> float:
    raise NotImplementedError


def bassqi(x: np.ndarray, fs: int = 360) -> float:
    raise NotImplementedError


def window_sqis(x: np.ndarray, r_pt: np.ndarray, r_mh: np.ndarray, fs: int = 360) -> np.ndarray:
    """Log of the four SQIs for one window, in the order q, p, k, bas."""
    x = x - x.mean()
    raw = np.array([qsqi(r_pt, r_mh, fs), psqi(x, fs), ksqi(x), bassqi(x, fs)])
    return np.log(np.clip(raw, 1e-12, None))
