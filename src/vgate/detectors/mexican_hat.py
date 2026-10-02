"""Mexican-hat (Ricker) detector, used only for qSQI.

Spec: causal FIR, sigma = 25 ms, threshold at 40 % of the running 2 s maximum.
"""

from __future__ import annotations

import numpy as np


def detect(x: np.ndarray, fs: int = 360) -> np.ndarray:
    raise NotImplementedError
