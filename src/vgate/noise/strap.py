"""Noise recorded from the team's own AD8232 / ESP32-S3 strap.

Used for the fresh-data re-test (docs/strap_noise_protocol.md). Recordings are
resampled to the pipeline rate and checked for ECG contamination: a noise record that
still contains the volunteer's heartbeat would add a second ECG when mixed into
MIT-BIH. Amplitude units do not matter, because the mixer scales noise to the target
SNR from its own power.
"""

from __future__ import annotations

from fractions import Fraction

import numpy as np
from scipy import signal

from vgate import config
from vgate.detectors import pan_tompkins

# A heartbeat looks like regular detections: at least 0.5 per second (30 bpm)
# with RR intervals varying by less than this coefficient of variation.
MIN_RATE_HZ = 0.5
MAX_RR_CV = 0.15


def to_pipeline_rate(x: np.ndarray, fs_in: float) -> np.ndarray:
    """Resample to [fs] (360 Hz) with a polyphase filter; the mean is removed first."""
    fs = config.pipeline()["fs"]
    x = np.asarray(x, float) - np.mean(x)
    if fs_in == fs:
        return x
    ratio = Fraction(fs, 1) / Fraction(fs_in).limit_denominator(1000)
    return signal.resample_poly(x, ratio.numerator, ratio.denominator)


def heartbeat_check(x: np.ndarray, fs: int = 360, chunk_s: float = 60.0) -> dict:
    """Flag ECG contamination, minute by minute.

    A chunk is contaminated when Pan-Tompkins finds >= MIN_RATE_HZ detections per
    second with RR coefficient of variation < MAX_RR_CV. Returns per-chunk flags and
    the contaminated fraction.
    """
    n = int(chunk_s * fs)
    flags = []
    for start in range(0, len(x) - n + 1, n):
        r = pan_tompkins.detect(x[start : start + n], fs)
        rr = np.diff(r) / fs
        regular = len(rr) >= 3 and np.std(rr) / np.mean(rr) < MAX_RR_CV
        flags.append(bool(len(r) / chunk_s >= MIN_RATE_HZ and regular))
    return {"chunks": flags, "contaminated_fraction": float(np.mean(flags)) if flags else 0.0}
