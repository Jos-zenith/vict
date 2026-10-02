"""Per-beat features: RR before/after, mean of last 10 RR, QRS width, R and S
amplitude, db4 band energies over -250..+450 ms (truncated at neighbour midpoints).
Owner: Chandru.
"""

from __future__ import annotations

import numpy as np


def beat_features(x: np.ndarray, r_peaks: np.ndarray, fs: int = 360) -> np.ndarray:
    """Feature matrix, one row per detected beat."""
    raise NotImplementedError
