"""Per-window table: the interface between the classifier and everything after it.

One row per 10 s decision window per record copy. Gate training, risky-window
labels, threshold sweeps, matched retention, the bootstrap and coverage all work
from this table; nothing downstream goes back to beat level.

Record copies:
  clean  the original record (noise_type "none", offset -1, snr_db NaN)
  noisy  the record mixed with one NSTDB noise type using schedule cycle offset
         ``offset``; windows in its clean segments have snr_db NaN

Threshold-dependent counts are (n_windows, n_thresholds) matrices over the sweep in
configs/pipeline.toml [thresholds]. A beat is called V when its SVM decision value
is > threshold.

Scoring (detections matched to reference beats with evaluation.matching at
+/- [scoring] match_tolerance_ms; each beat counts in the window it falls in):
  n_true_v  reference V beats annotated in the window
  n_pred_v  detections in the window called V
  false_v   of those, detections matched to nothing or to an N/S/F beat
            (calls on reference Q beats are neither true nor false)
  lost_v    reference V beats in the window that the detector missed or whose
            matched detection is not called V
  risky     error-risk label (the gates' target): at the default threshold, noise
            added a false V or lost a true V relative to the same window of the
            paired clean copy (same record, same classifier):
              false_v > clean false_v  or  lost_v > clean lost_v
            Always False on the clean copy. Errors the classifier also makes on clean
            signal (e.g. bundle-branch beats called V) are therefore not risk.

Stored as .npz under results/ with WindowTable.save / WindowTable.load.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np

from vgate import config
from vgate.evaluation.matching import match
from vgate.models.gates import confidence_features

SPLITS = ("train", "cal", "test")
COPIES = ("clean", "noisy")
NOISE_TYPES = ("none", "em", "ma", "bw")
MARGIN_COLUMNS = ("svm_margin_min", "svm_margin_mean", "svm_margin_p10")
SQI_COLUMNS = ("log_qsqi", "log_psqi", "log_ksqi", "log_bassqi")
COUNT_COLUMNS = ("n_pred_v", "false_v", "lost_v")


def thresholds() -> np.ndarray:
    """Decision-value sweep from the config; always contains the default threshold."""
    t = config.pipeline()["thresholds"]
    start, stop, step = t["sweep"]
    grid = np.round(np.arange(start, stop + step / 2, step), 6)
    if not np.isclose(grid, t["default"]).any():
        raise ValueError("[thresholds] sweep must contain the default threshold")
    return grid


def default_index(thr: np.ndarray) -> int:
    return int(np.argmin(np.abs(thr - config.pipeline()["thresholds"]["default"])))


def window_starts(n_samples: int, fs: int = 360) -> np.ndarray:
    """Start sample of each full, non-overlapping window (first dropped if the config says so)."""
    p = config.pipeline()
    win = p["window_s"] * fs
    starts = np.arange(0, n_samples - win + 1, win)
    return starts[1:] if p["filter"]["skip_first_window"] else starts


def _window_of(samples: np.ndarray, starts: np.ndarray, win: int) -> tuple[np.ndarray, np.ndarray]:
    """Window index of each sample, and whether it falls inside any window."""
    w = np.clip(np.searchsorted(starts, samples, side="right") - 1, 0, None)
    ok = (samples >= starts[0]) & (samples < starts[w] + win)
    return w, ok


def v_counts(
    det: np.ndarray,
    decision: np.ndarray,
    ref_sample: np.ndarray,
    ref_aami: np.ndarray,
    starts: np.ndarray,
    win: int,
    thr: np.ndarray,
    tol: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Score V calls per window and threshold.

    Returns n_true_v (W,) and n_pred_v, false_v, lost_v, each (W, K).
    """
    det, ref_sample = np.asarray(det, int), np.asarray(ref_sample, int)
    ref_aami = np.asarray(ref_aami, str)
    n_win, n_thr = len(starts), len(thr)

    d2r, r2d = match(det, ref_sample, tol)
    called = np.asarray(decision, float)[:, None] > np.asarray(thr)[None, :]
    det_cls = np.full(len(det), "-", dtype="U1")
    det_cls[d2r >= 0] = ref_aami[d2r[d2r >= 0]]
    false = called & ~np.isin(det_cls, ["V", "Q"])[:, None]

    n_pred = np.zeros((n_win, n_thr), int)
    n_false = np.zeros((n_win, n_thr), int)
    w, ok = _window_of(det, starts, win)
    np.add.at(n_pred, w[ok], called[ok])
    np.add.at(n_false, w[ok], false[ok])

    hit = np.zeros((len(ref_sample), n_thr), bool)
    m = r2d >= 0
    hit[m] = called[r2d[m]]
    w, ok = _window_of(ref_sample, starts, win)
    ok &= ref_aami == "V"
    n_true = np.bincount(w[ok], minlength=n_win)
    n_lost = np.zeros((n_win, n_thr), int)
    np.add.at(n_lost, w[ok], ~hit[ok])
    return n_true, n_pred, n_false, n_lost


# dtype kind per column: i = integer, f = float, U = string, b = bool
_KIND = {
    "record": "i", "split": "U", "copy": "U", "noise_type": "U", "offset": "i",
    "snr_db": "f", "t0": "i", "n_beats": "i",
    **dict.fromkeys(MARGIN_COLUMNS + SQI_COLUMNS, "f"),
    "n_true_v": "i", **dict.fromkeys(COUNT_COLUMNS, "i"), "risky": "b",
}  # fmt: skip


@dataclass
class WindowTable:
    record: np.ndarray           # MIT-BIH record number
    split: np.ndarray            # train | cal | test
    copy: np.ndarray             # clean | noisy
    noise_type: np.ndarray       # none | em | ma | bw
    offset: np.ndarray           # noise schedule cycle offset; -1 on the clean copy
    snr_db: np.ndarray           # target SNR of the noisy segment holding the window, else NaN
    t0: np.ndarray               # window start, whole seconds from record start
    n_beats: np.ndarray          # Pan-Tompkins detections in the window
    svm_margin_min: np.ndarray   # |SVM decision value| over the window's beats,
    svm_margin_mean: np.ndarray  #   as gates.confidence_features (0 when n_beats == 0)
    svm_margin_p10: np.ndarray
    log_qsqi: np.ndarray         # sqi.window_sqis, natural log
    log_psqi: np.ndarray
    log_ksqi: np.ndarray
    log_bassqi: np.ndarray
    n_true_v: np.ndarray         # (N,)
    n_pred_v: np.ndarray         # (N, K) one column per threshold
    false_v: np.ndarray          # (N, K)
    lost_v: np.ndarray           # (N, K)
    risky: np.ndarray            # noise added a false V or lost a true V vs the clean copy
    thresholds: np.ndarray       # (K,) shared by every row

    def __len__(self) -> int:
        return len(self.record)

    @property
    def default_index(self) -> int:
        return default_index(self.thresholds)

    def gate_features(self, sqi: bool = False) -> np.ndarray:
        """Gc inputs (margin min, mean, p10, n_beats); with ``sqi`` the Gcs inputs."""
        cols = [*MARGIN_COLUMNS, "n_beats", *(SQI_COLUMNS if sqi else ())]
        return np.column_stack([getattr(self, c).astype(float) for c in cols])

    def subset(self, mask: np.ndarray) -> WindowTable:
        return WindowTable(**{
            f.name: getattr(self, f.name) if f.name == "thresholds" else getattr(self, f.name)[mask]
            for f in fields(self)
        })  # fmt: skip

    @classmethod
    def concat(cls, tables: list[WindowTable]) -> WindowTable:
        thr = tables[0].thresholds
        if any(not np.array_equal(t.thresholds, thr) for t in tables):
            raise ValueError("tables use different threshold sweeps")
        return cls(**{
            f.name: thr if f.name == "thresholds"
            else np.concatenate([getattr(t, f.name) for t in tables])
            for f in fields(cls)
        })  # fmt: skip

    def validate(self) -> None:
        """Raise ValueError if the table breaks the contract in the module docstring."""
        n, k = len(self), len(self.thresholds)

        def check(ok: bool, msg: str) -> None:
            if not ok:
                raise ValueError(msg)

        for name, kind in _KIND.items():
            a = getattr(self, name)
            shape = (n, k) if name in COUNT_COLUMNS else (n,)
            check(a.shape == shape, f"{name}: shape {a.shape}, expected {shape}")
            check(a.dtype.kind in {"i": "iu"}.get(kind, kind), f"{name}: dtype {a.dtype}")
        check(bool(np.all(np.diff(self.thresholds) > 0)), "thresholds must increase")
        check(set(self.split) <= set(SPLITS), f"split outside {SPLITS}")
        check(set(self.copy) <= set(COPIES), f"copy outside {COPIES}")
        check(set(self.noise_type) <= set(NOISE_TYPES), f"noise_type outside {NOISE_TYPES}")

        clean = self.copy == "clean"
        check(bool(np.all((self.noise_type == "none") == clean)), "noise_type none <=> clean copy")
        check(bool(np.all((self.offset == -1) == clean)), "offset -1 <=> clean copy")
        check(bool(np.all(np.isnan(self.snr_db[clean]))), "clean copy must have snr_db NaN")

        keys = np.rec.fromarrays([self.record, self.copy, self.noise_type, self.offset, self.t0])
        check(len(np.unique(keys)) == n, "duplicate (record, copy, noise_type, offset, t0)")

        check(bool(np.all(np.diff(self.n_pred_v, axis=1) <= 0)), "n_pred_v rises with threshold")
        check(bool(np.all(self.false_v <= self.n_pred_v)), "false_v > n_pred_v")
        check(bool(np.all(self.n_pred_v <= self.n_beats[:, None])), "n_pred_v > n_beats")
        check(bool(np.all(self.lost_v <= self.n_true_v[:, None])), "lost_v > n_true_v")
        check(not self.risky[clean].any(), "clean-copy windows cannot be risky")
        d = self.default_index
        pairs = zip(self.record[clean], self.t0[clean], strict=True)
        ckey = {(r, t): i for i, (r, t) in enumerate(pairs)}
        cfv, clost = self.false_v[clean, d], self.lost_v[clean, d]
        for i in np.flatnonzero(~clean):
            j = ckey.get((self.record[i], self.t0[i]))
            if j is not None:  # clean pair present: the label must follow from it
                want = self.false_v[i, d] > cfv[j] or self.lost_v[i, d] > clost[j]
                check(bool(self.risky[i]) == bool(want), "risky disagrees with the clean pair")

    def save(self, path: str | Path) -> None:
        self.validate()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **{f.name: getattr(self, f.name) for f in fields(self)})

    @classmethod
    def load(cls, path: str | Path) -> WindowTable:
        with np.load(path, allow_pickle=False) as z:
            table = cls(**{f.name: z[f.name] for f in fields(cls)})
        table.validate()
        return table


def risky_vs_clean(
    copy: str,
    t0: np.ndarray,
    false: np.ndarray,
    lost: np.ndarray,
    thr: np.ndarray,
    clean: WindowTable | None,
) -> np.ndarray:
    """Error-risk label per window (see module docstring)."""
    if copy == "clean":
        return np.zeros(len(t0), bool)
    if clean is None:
        raise ValueError("a noisy copy needs its clean copy to label risky windows")
    d = default_index(thr)
    pos = {t: i for i, t in enumerate(clean.t0)}
    missing = [t for t in t0 if t not in pos]
    if missing:
        raise ValueError(f"clean copy lacks windows at t0 = {missing[:5]}")
    j = np.array([pos[t] for t in t0], dtype=int)
    return (false[:, d] > clean.false_v[j, d]) | (lost[:, d] > clean.lost_v[j, d])


def from_record(
    *,
    record: int,
    split: str,
    copy: str,
    noise_type: str,
    offset: int,
    starts: np.ndarray,
    snr_db: np.ndarray,
    sqis: np.ndarray,
    det: np.ndarray,
    decision: np.ndarray,
    ref_sample: np.ndarray,
    ref_aami: np.ndarray,
    fs: int = 360,
    clean: WindowTable | None = None,
) -> WindowTable:
    """Rows for one record copy.

    clean: rows of the same record's clean copy scored with the same classifier;
    required for a noisy copy, to label risky windows.

    starts: window_starts(); snr_db: (W,) per window; sqis: (W, 4) from sqi.window_sqis;
    det, decision: Pan-Tompkins R peaks and the classifier's decision value for each.
    """
    p = config.pipeline()
    win = p["window_s"] * fs
    tol = round(p["scoring"]["match_tolerance_ms"] * fs / 1000)
    thr = thresholds()
    det, decision = np.asarray(det, int), np.asarray(decision, float)
    n_win = len(starts)

    w, ok = _window_of(det, starts, win)
    margins = np.array([confidence_features(decision[ok & (w == i)]) for i in range(n_win)])
    margins = margins.reshape(n_win, 4)
    n_true, n_pred, false, lost = v_counts(
        det, decision, ref_sample, ref_aami, starts, win, thr, tol
    )
    sqis = np.asarray(sqis, float).reshape(n_win, 4)

    table = WindowTable(
        record=np.full(n_win, record),
        split=np.full(n_win, split),
        copy=np.full(n_win, copy),
        noise_type=np.full(n_win, noise_type),
        offset=np.full(n_win, offset),
        snr_db=np.asarray(snr_db, float),
        t0=np.asarray(starts) // fs,
        n_beats=margins[:, 3].astype(int),
        svm_margin_min=margins[:, 0],
        svm_margin_mean=margins[:, 1],
        svm_margin_p10=margins[:, 2],
        log_qsqi=sqis[:, 0],
        log_psqi=sqis[:, 1],
        log_ksqi=sqis[:, 2],
        log_bassqi=sqis[:, 3],
        n_true_v=n_true,
        n_pred_v=n_pred,
        false_v=false,
        lost_v=lost,
        risky=risky_vs_clean(copy, starts // fs, false, lost, thr, clean),
        thresholds=thr,
    )
    table.validate()
    return table
