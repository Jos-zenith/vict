"""Per-beat features: RR before/after, mean of last 10 RR, QRS width, R and S
amplitude, db4 band energies over -250..+450 ms (truncated at neighbour midpoints).

RR values are capped at [windowing] censored_rr_s; the RR after the last beat (or
one longer than the cap, i.e. the decision timed out) is the cap. The first beat
uses its RR after as its RR before. Two prematurity ratios (RR / mean of last 10)
are added because a linear SVM cannot form them and they carry most of the
inter-patient V signal. Band energies are log(sum of squared coefficients) of a
5-level db4 decomposition (A5, D5..D1) of the zero-padded segment.
Owner: Chandru.
"""

from __future__ import annotations

import numpy as np
import pywt

from vgate import config

FEATURE_NAMES = (
    "rr_pre", "rr_post", "rr_avg10", "rr_pre_ratio", "rr_post_ratio", "qrs_width",
    "r_amp", "s_amp", "e_a5", "e_d5", "e_d4", "e_d3", "e_d2", "e_d1",
)  # fmt: skip


def beat_features(
    x: np.ndarray, r_peaks: np.ndarray, fs: int = 360, qrs_width: np.ndarray | None = None
) -> np.ndarray:
    """Feature matrix, one row per detected beat (columns: FEATURE_NAMES).

    x: classifier-filtered signal. qrs_width: integrator widths from the detector;
    if None they are measured offline at the given peaks.
    """
    cfg = config.pipeline()
    fc, wc = cfg["features"], cfg["windowing"]
    r = np.asarray(r_peaks, int)
    n = len(r)
    if n == 0:
        return np.zeros((0, len(FEATURE_NAMES)))
    if qrs_width is None:
        from vgate.detectors.pan_tompkins import integrator_widths

        qrs_width = integrator_widths(x, r, fs)

    cap = wc["censored_rr_s"]
    rr = np.minimum(np.diff(r) / fs, cap)
    rr_post = np.append(rr, cap)
    rr_pre = np.insert(rr, 0, rr_post[0])
    k = fc["rr_history"]
    c = np.cumsum(np.insert(rr_pre, 0, 0.0))
    lo = np.maximum(np.arange(1, n + 1) - k, 0)
    rr_avg = (c[1:] - c[lo]) / (np.arange(1, n + 1) - lo)

    rs, ss = round(fc["r_search_ms"] * fs / 1000), round(fc["s_search_ms"] * fs / 1000)
    w0, w1 = (round(v * fs / 1000) for v in fc["wavelet_span_ms"])
    seg_len = w1 - w0 + 1
    level = 5
    out = np.zeros((n, len(FEATURE_NAMES)))
    for i, p in enumerate(r):
        a, b = max(p - rs, 0), min(p + rs + 1, len(x))
        ri = a + int(np.argmax(x[a:b]))
        s_end = min(ri + ss + 1, len(x))
        s_amp = float(x[ri:s_end].min())

        left = p + w0 if i == 0 else max(p + w0, (r[i - 1] + p) // 2)
        right = p + w1 if i == n - 1 else min(p + w1, (p + r[i + 1]) // 2)
        left, right = max(left, 0), min(right, len(x) - 1)
        seg = np.zeros(seg_len)
        seg[left - (p + w0) : right - (p + w0) + 1] = x[left : right + 1]
        coeffs = pywt.wavedec(seg, fc["wavelet"], level=level)
        energies = [np.log(np.sum(cf**2) + 1e-9) for cf in coeffs]

        out[i] = [rr_pre[i], rr_post[i], rr_avg[i], rr_pre[i] / rr_avg[i], rr_post[i] / rr_avg[i],
                  qrs_width[i], x[ri], s_amp, *energies]  # fmt: skip
    return out
