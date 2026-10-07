"""Part 2 acceptance: Pan-Tompkins sensitivity and PPV >= 0.99 on clean DS1.

Detections are scored against all reference beats (AAMI N/S/V/F/Q) with
evaluation.matching at [scoring] match_tolerance_ms.
"""

from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor

from vgate import config
from vgate.data import mitdb
from vgate.detectors import pan_tompkins
from vgate.evaluation.matching import match


def score(record: int) -> tuple[int, int, int, int, float]:
    rec = mitdb.load_record(record)
    t = time.perf_counter()
    det = pan_tompkins.detect(rec.signal, rec.fs)
    dt = time.perf_counter() - t
    tol = round(config.pipeline()["scoring"]["match_tolerance_ms"] * rec.fs / 1000)
    d2r, r2d = match(det, rec.ann_sample, tol)
    tp = int((r2d >= 0).sum())
    return record, tp, len(rec.ann_sample) - tp, len(det) - tp, dt


def main() -> None:
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(score, mitdb.ds1()))
    print(f"{'rec':>4} {'TP':>6} {'FN':>5} {'FP':>5} {'Se':>7} {'PPV':>7} {'sec':>5}")
    for r, tp, fn, fp, dt in rows:
        se, ppv = tp / (tp + fn), tp / max(tp + fp, 1)
        print(f"{r:4d} {tp:6d} {fn:5d} {fp:5d} {se:7.4f} {ppv:7.4f} {dt:5.1f}")
    tp, fn, fp = (sum(x[i] for x in rows) for i in (1, 2, 3))
    se, ppv = tp / (tp + fn), tp / (tp + fp)
    print(
        f"DS1 gross: Se {se:.4f}  PPV {ppv:.4f}  ->  {'PASS' if min(se, ppv) >= 0.99 else 'FAIL'}"
    )


if __name__ == "__main__":
    main()
