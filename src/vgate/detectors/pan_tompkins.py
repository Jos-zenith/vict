"""Pan-Tompkins QRS detector redesigned for 360 Hz.

Spec (configs/pipeline.toml [pan_tompkins]): 5-15 Hz band-pass, derivative,
squaring, 150 ms moving-window integrator, the published adaptive thresholds and
a 200 ms refractory period. Must be streaming (samples in, detections out) so the
C port is a line-by-line translation.
"""

from __future__ import annotations

import numpy as np


class PanTompkins:
    def __init__(self, fs: int = 360) -> None:
        self.fs = fs

    def reset(self) -> None:
        raise NotImplementedError

    def push(self, x: np.ndarray) -> list[int]:
        """Feed a chunk of samples; return absolute indices of new R-peak detections."""
        raise NotImplementedError

    def qrs_width(self, r_index: int) -> float:
        """QRS width (s) from the integrator, for the beat feature vector."""
        raise NotImplementedError


def detect(x: np.ndarray, fs: int = 360) -> np.ndarray:
    """Offline wrapper: run the streaming detector over a whole record."""
    det = PanTompkins(fs)
    return np.asarray(det.push(x), dtype=int)
