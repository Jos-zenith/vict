# Phase 1 study: can the fallback design be frozen? Results

Pre-registered in `docs/qsqi_deferral_plan.md` (committed before this run). DS1 only; per held-out noise type, pooled over its six record folds. FV/h = false V calls per hour; ret = V retention; kept = windows kept.

## D0 a priori

| held-out | SVM thr (mean) | q* (mean) | kept | ret (floor) | FV/h with / without deferral | reduction | deferred: qSQI only / few beats | T1 | T2 | T3 | T4 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| em | +0.00 | 0.800 | 90.9% | 0.635 (0.617) | 857 / 1102 | +22.2% | 9.1% / 0.0% | pass | pass | pass | pass |
| ma | +0.00 | 0.800 | 87.9% | 0.525 (0.492) | 405 / 544 | +25.6% | 12.1% / 0.0% | pass | pass | pass | pass |
| bw | +0.00 | 0.800 | 97.4% | 0.657 (0.593) | 602 / 650 | +7.4% | 2.6% / 0.0% | pass | pass | FAIL | pass |

**D0 a priori: cannot be frozen.**

## D1 calibrated deferral

| held-out | SVM thr (mean) | q* (mean) | kept | ret (floor) | FV/h with / without deferral | reduction | deferred: qSQI only / few beats | T1 | T2 | T3 | T4 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| em | +0.00 | 0.829 | 87.1% | 0.586 (0.617) | 750 / 1102 | +32.0% | 12.9% / 0.0% | pass | FAIL | pass | pass |
| ma | +0.00 | 0.840 | 83.0% | 0.496 (0.492) | 373 / 544 | +31.5% | 17.0% / 0.0% | pass | pass | pass | pass |
| bw | +0.00 | 0.829 | 96.2% | 0.634 (0.593) | 593 / 650 | +8.9% | 3.8% / 0.0% | pass | pass | FAIL | pass |

**D1 calibrated deferral: cannot be frozen.**

## D2 calibrated threshold

| held-out | SVM thr (mean) | q* (mean) | kept | ret (floor) | FV/h with / without deferral | reduction | deferred: qSQI only / few beats | T1 | T2 | T3 | T4 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| em | +0.01 | 0.800 | 90.9% | 0.592 (0.617) | 873 / 1111 | +21.4% | 9.1% / 0.0% | pass | FAIL | pass | pass |
| ma | +0.05 | 0.800 | 87.9% | 0.487 (0.492) | 385 / 515 | +25.2% | 12.1% / 0.0% | pass | FAIL | pass | pass |
| bw | +0.01 | 0.800 | 97.4% | 0.632 (0.593) | 612 / 659 | +7.2% | 2.6% / 0.0% | pass | pass | FAIL | pass |

**D2 calibrated threshold: cannot be frozen.**

## Context (not used to pass or fail)

| held-out | Robust default: FV/h, ret | raised threshold (M0): FV/h, ret | Gcs (M0): FV/h, ret, kept |
|---|---|---|---|
| em | 1102, 0.708 | 988, 0.598 | 954, 0.699, 97% |
| ma | 544, 0.569 | 450, 0.491 | 338, 0.480, 76% |
| bw | 650, 0.681 | 581, 0.593 | 303, 0.584, 79% |

## Decision

**No method passes** (decision rule 2): the fallback cannot be frozen with fixed settings. The team chooses between threshold-only (retention drift documented) and a pre-registered adaptive-calibration study.
