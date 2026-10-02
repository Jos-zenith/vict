"""NSTDB-style noise mixer.

Acceptance (Objectives table): reproduce NSTDB 118e12 from 118 + em at 12 dB with
sample-wise RMS difference < 1 % of signal RMS, and every per-block mixture's
measured SNR within 0.5 dB of its target.
"""

from __future__ import annotations

import numpy as np


def signal_power(x: np.ndarray, r_peaks: np.ndarray, fs: int = 360, n_qrs: int = 300) -> float:
    """nst definition: (trimmed mean p-p amplitude of the first n_qrs normal QRS)^2 / 8."""
    raise NotImplementedError


def noise_power(noise: np.ndarray, fs: int = 360) -> float:
    """Mean power over 1 s chunks, each with its own mean removed."""
    raise NotImplementedError


def noise_scale(s_power: float, n_power: float, snr_db: float) -> float:
    """Gain applied to the noise so that the mixture has the target SNR."""
    return float(np.sqrt(s_power / (n_power * 10 ** (snr_db / 10))))


def build_schedule(n_samples: int, fs: int, blocks: list[int], offset: int) -> list[dict]:
    """5 clean min, then alternating 2 min clean / noisy, cycling SNRs and blocks."""
    raise NotImplementedError


def mix(x: np.ndarray, noise: np.ndarray, schedule: list[dict], fs: int = 360) -> np.ndarray:
    """Apply a schedule at 360 Hz before any filtering, with 1 s ramps at segment edges."""
    raise NotImplementedError
