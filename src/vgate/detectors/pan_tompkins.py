"""Pan-Tompkins QRS detector redesigned for 360 Hz.

Spec (configs/pipeline.toml [pan_tompkins]): 5-15 Hz band-pass, derivative,
squaring, 150 ms moving-window integrator, the published adaptive thresholds and
a 200 ms refractory period. Must be streaming (samples in, detections out) so the
C port is a line-by-line translation.

Decision logic (Pan & Tompkins 1985, integrator channel):
  - learning phase: first 2 s set SPKI = max/3, NPKI = mean/2, then are replayed
  - a peak is the integrator maximum, emitted once the signal falls to half of it
  - peaks within the refractory period are ignored
  - 200-360 ms after a QRS, a peak whose maximum slope is under half the previous
    QRS's is a T wave (noise)
  - peak > THR1 -> QRS (SPKI += (peak - SPKI) / 8), else noise (NPKI likewise)
  - search-back: no QRS for 166 % of RR average 2 -> the largest noise peak since
    the last QRS becomes a QRS if it exceeds THR2 = THR1 / 2 (SPKI += (peak - SPKI) / 4)
  - THR1 is halved while the rhythm is irregular (last RR outside 92-116 % of RR avg 2)
  - lock-out guard (not in the paper): no QRS for 2 x the search-back limit
    re-runs the learning step on the last 2 s
The R peak is the largest |band-pass| sample in the integrator window before the
peak, corrected for the band-pass group delay.
"""

from __future__ import annotations

from collections import deque

import numpy as np
from scipy import signal

from vgate import config

LEARN_S = 2.0
T_WAVE_S = 0.36
HISTORY_S = 3.0


def _design(fs: int) -> tuple[np.ndarray, np.ndarray, int, int]:
    cfg = config.pipeline()["pan_tompkins"]
    sos = signal.butter(2, cfg["band_hz"], btype="bandpass", fs=fs, output="sos")
    der = np.array([2.0, 1.0, 0.0, -1.0, -2.0]) * fs / 8
    n_mwi = round(cfg["mwi_ms"] * fs / 1000)
    b, a = signal.sos2tf(sos)
    bp_delay = round(float(signal.group_delay((b, a), w=[10.0], fs=fs)[1][0]))
    return sos, der, n_mwi, bp_delay


def front_end(x: np.ndarray, fs: int = 360) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Offline band-pass, derivative and integrator signals (same filters as the detector)."""
    sos, der, n_mwi, _ = _design(fs)
    x = np.asarray(x, float)
    bp = signal.sosfilt(sos, x, zi=signal.sosfilt_zi(sos) * x[0])[0]
    d = signal.lfilter(der, 1.0, bp)
    mwi = signal.lfilter(np.ones(n_mwi) / n_mwi, 1.0, d * d)
    return bp, d, mwi


def integrator_width(mwi: np.ndarray, peak: int, n_mwi: int, fs: int) -> float:
    """QRS width (s): integrator rising edge from 10 % to 90 % of the peak, / 0.8."""
    lo = max(peak - 2 * n_mwi, 0)
    seg = mwi[lo : peak + 1]
    if len(seg) < 2 or seg[-1] <= 0:
        return 0.0
    v = seg[-1]
    below10 = np.flatnonzero(seg < 0.1 * v)
    t10 = below10[-1] + 1 if len(below10) else 0
    t90 = t10 + int(np.argmax(seg[t10:] >= 0.9 * v))
    return (t90 - t10) / 0.8 / fs


def integrator_widths(x: np.ndarray, r_peaks: np.ndarray, fs: int = 360) -> np.ndarray:
    """integrator_width at each given R peak (e.g. reference annotations)."""
    _, _, n_mwi, bp_delay = _design(fs)
    _, _, mwi = front_end(x, fs)
    out = np.zeros(len(r_peaks))
    for i, r in enumerate(np.asarray(r_peaks, int)):
        lo, hi = r, min(r + n_mwi + bp_delay + 10, len(mwi))
        if hi > lo:
            out[i] = integrator_width(mwi, lo + int(np.argmax(mwi[lo:hi])), n_mwi, fs)
    return out


class PanTompkins:
    def __init__(self, fs: int = 360) -> None:
        self.fs = fs
        self.sos, self.der, self.n_mwi, self.bp_delay = _design(fs)
        cfg = config.pipeline()["pan_tompkins"]
        self.refractory = round(cfg["refractory_ms"] * fs / 1000)
        self.t_wave = round(T_WAVE_S * fs)
        self.n_learn = round(LEARN_S * fs)
        self.n_hist = round(HISTORY_S * fs)
        self.reset()

    def reset(self) -> None:
        self.n = 0  # samples consumed
        self.zi_bp: np.ndarray | None = None
        self.zi_der = np.zeros(len(self.der) - 1)
        self.zi_mwi = np.zeros(self.n_mwi - 1)
        self.h0 = 0  # absolute index of history[0]
        self.h_bp = np.zeros(0)
        self.h_der = np.zeros(0)
        self.h_mwi = np.zeros(0)
        self.learning = True
        self.spki = self.npki = 0.0
        self.pk_val, self.pk_idx, self.armed = 0.0, -1, True
        self.prev = 0.0
        self.last_qrs: int | None = None  # integrator peak of the last QRS
        self.last_slope = 0.0
        self.last_relearn = 0
        self.rr1: deque[int] = deque(maxlen=8)
        self.rr2: deque[int] = deque(maxlen=8)
        self.irregular = False
        self.cand: tuple[int, float] | None = None  # best noise peak for search-back
        self.widths: dict[int, float] = {}
        self._out: list[int] = []

    # --- thresholds -------------------------------------------------------------
    def _thr1(self) -> float:
        t = self.npki + 0.25 * (self.spki - self.npki)
        return 0.5 * t if self.irregular else t

    def _missed_limit(self) -> float:
        rr = self.rr2 or self.rr1
        return 1.66 * (sum(rr) / len(rr) if rr else self.fs)

    def _learn(self, end: int) -> None:
        seg = self.h_mwi[max(end - self.n_learn - self.h0, 0) : end - self.h0]
        self.spki, self.npki = seg.max() / 3, seg.mean() / 2

    # --- history access (absolute indices) --------------------------------------
    def _hist(self, buf: np.ndarray, lo: int, hi: int) -> np.ndarray:
        return buf[max(lo - self.h0, 0) : max(hi - self.h0, 0)]

    # --- events -----------------------------------------------------------------
    def _qrs(self, p: int, v: float, searchback: bool) -> None:
        a = 0.25 if searchback else 0.125
        self.spki += a * (v - self.spki)
        lo = p - self.n_mwi - self.bp_delay - 5
        bp = self._hist(self.h_bp, lo, p + 1)
        start = max(lo, self.h0)
        r = start + int(np.argmax(np.abs(bp))) - self.bp_delay if len(bp) else p
        self.last_slope = float(np.max(np.abs(self._hist(self.h_der, lo, p + 1)), initial=0.0))
        if self.last_qrs is not None:
            rr = p - self.last_qrs
            self.rr1.append(rr)
            avg2 = sum(self.rr2) / len(self.rr2) if self.rr2 else rr
            ok = 0.92 * avg2 <= rr <= 1.16 * avg2
            if ok or not self.rr2:
                self.rr2.append(rr)
            self.irregular = not ok
        self.last_qrs = p
        self.cand = None
        r = max(r, 0)
        self.widths[r] = integrator_width(self.h_mwi, p - self.h0, self.n_mwi, self.fs)
        self._out.append(r)

    def _peak(self, p: int, v: float) -> None:
        last = self.last_qrs
        if last is not None and p - last < self.refractory:
            return
        if last is not None and p - last < self.t_wave:
            lo = p - self.n_mwi - self.bp_delay - 5
            slope = float(np.max(np.abs(self._hist(self.h_der, lo, p + 1)), initial=0.0))
            if slope < 0.5 * self.last_slope:
                self.npki += 0.125 * (v - self.npki)
                return
        if v > self._thr1():
            self._qrs(p, v, searchback=False)
        else:
            self.npki += 0.125 * (v - self.npki)
            if self.cand is None or v > self.cand[1]:
                self.cand = (p, v)

    def _step(self, i: int, v: float) -> None:
        if v > self.pk_val and self.armed:
            self.pk_val, self.pk_idx = v, i
        elif self.pk_val > 0 and v < 0.5 * self.pk_val:
            self._peak(self.pk_idx, self.pk_val)
            self.pk_val, self.armed = 0.0, False
        if not self.armed and v > self.prev:
            self.armed = True
            self.pk_val, self.pk_idx = v, i
        self.prev = v

        ref = self.last_qrs if self.last_qrs is not None else self.n_learn
        gap = i - ref
        limit = self._missed_limit()
        if gap > limit and self.cand is not None and self.cand[1] > 0.5 * self._thr1():
            p, pv = self.cand
            self._qrs(p, pv, searchback=True)
        elif gap > 2 * limit and i - self.last_relearn > self.n_learn:
            self._learn(i + 1)
            self.last_relearn = i

    # --- streaming interface ----------------------------------------------------
    def push(self, x: np.ndarray) -> list[int]:
        """Feed a chunk of samples; return absolute indices of new R-peak detections."""
        x = np.asarray(x, float)
        if len(x) == 0:
            return []
        if self.zi_bp is None:
            self.zi_bp = signal.sosfilt_zi(self.sos) * x[0]
        bp, self.zi_bp = signal.sosfilt(self.sos, x, zi=self.zi_bp)
        d, self.zi_der = signal.lfilter(self.der, 1.0, bp, zi=self.zi_der)
        mwi, self.zi_mwi = signal.lfilter(
            np.ones(self.n_mwi) / self.n_mwi, 1.0, d * d, zi=self.zi_mwi
        )

        start = self.n
        self.n += len(x)
        self.h_bp = np.concatenate([self.h_bp, bp])
        self.h_der = np.concatenate([self.h_der, d])
        self.h_mwi = np.concatenate([self.h_mwi, mwi])
        self._out = []

        if self.learning:
            if self.n < self.n_learn:
                return []
            self.learning = False
            self._learn(self.n_learn)
            self.last_relearn = self.n_learn
            begin = self.h0  # replay the buffered learning phase
        else:
            begin = start
        h_mwi, h0 = self.h_mwi, self.h0
        for i in range(begin, self.n):
            self._step(i, float(h_mwi[i - h0]))

        excess = len(self.h_mwi) - max(self.n_hist, self.n_learn)
        if excess > 0:
            self.h_bp, self.h_der, self.h_mwi = (
                self.h_bp[excess:],
                self.h_der[excess:],
                self.h_mwi[excess:],
            )
            self.h0 += excess
        return sorted(self._out)

    def qrs_width(self, r_index: int) -> float:
        """QRS width (s) from the integrator, for the beat feature vector."""
        return self.widths.get(r_index, 0.0)


def detect_with_widths(
    x: np.ndarray, fs: int = 360, chunk: int = 3600
) -> tuple[np.ndarray, np.ndarray]:
    """Run the streaming detector in chunks; R peaks and their integrator QRS widths."""
    det = PanTompkins(fs)
    r: list[int] = []
    for k in range(0, len(x), chunk):
        r.extend(det.push(x[k : k + chunk]))
    r_arr = np.unique(np.asarray(r, dtype=int))
    return r_arr, np.array([det.qrs_width(int(i)) for i in r_arr])


def detect(x: np.ndarray, fs: int = 360) -> np.ndarray:
    """Offline wrapper: run the streaming detector over a whole record."""
    return detect_with_widths(x, fs)[0]
