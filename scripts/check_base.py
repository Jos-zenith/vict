"""Part 1 acceptance: Base V sensitivity >= 70 % in record-grouped CV on DS1-train.

Reference beat annotations stand in for the detector, so this checks features + SVM
alone. Q beats are left out of training and scoring.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

import numpy as np

from vgate.data import mitdb
from vgate.dsp.filters import bandpass
from vgate.features import beat_features
from vgate.models.classifiers import C_GRID, grouped_cv_predictions


def record_features(record: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rec = mitdb.load_record(record)
    X = beat_features(bandpass(rec.signal).astype(float), rec.ann_sample, rec.fs)
    keep = rec.ann_aami != "Q"
    return X[keep], (rec.ann_aami[keep] == "V").astype(int), np.full(keep.sum(), record)


def main() -> None:
    with ProcessPoolExecutor() as ex:
        parts = list(ex.map(record_features, mitdb.ds1_train()))
    X, y, g = (np.concatenate(p) for p in zip(*parts, strict=True))
    print(f"{len(y)} beats, {y.sum()} V, {len(set(g))} records")
    best = None
    for C in C_GRID:
        d = grouped_cv_predictions(X, y, g, C)
        se = ((d > 0) & (y == 1)).sum() / y.sum()
        fpr = ((d > 0) & (y == 0)).sum() / (y == 0).sum()
        ppv = ((d > 0) & (y == 1)).sum() / max((d > 0).sum(), 1)
        bacc = (se + 1 - fpr) / 2
        print(f"C={C:<6} V Se {se:.3f}  PPV {ppv:.3f}  FPR {fpr:.4f}  balanced acc {bacc:.3f}")
        if best is None or bacc > best[0]:
            best = (bacc, C, se)
    _, C, se = best
    print(f"selected C={C}: V Se {se:.3f} -> {'PASS' if se >= 0.70 else 'FAIL'}")


if __name__ == "__main__":
    main()
