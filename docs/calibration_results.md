# Phase 1 calibration study: results

Pre-registered in `docs/calibration_plan.md` (committed before this run). DS1 only; per held-out noise type, pooled over its six record folds. FV/h = false V calls per hour; ret = V retention; kept = windows kept. T2 is shown per arm (threshold/Gcs).

## M0 frozen rule

| held-out | target ret | threshold: FV/h, ret | Gc: FV/h, ret, kept | Gcs: FV/h, ret, kept | Gcs vs threshold (95 % CI) | Gcs vs Gc | T1 | T2 thr/Gcs | T3 |
|---|---|---|---|---|---|---|---|---|---|
| em | 0.637 | 988, 0.598 | 802, 0.645, 93% | 954, 0.699, 97% | +2.8% (-10%, +29%) | -19.0% | pass | FAIL/pass | pass |
| ma | 0.512 | 450, 0.491 | 163, 0.376, 70% | 338, 0.480, 76% | +22.6% (-2%, +85%) | -107.1% | FAIL | FAIL/FAIL | pass |
| bw | 0.613 | 581, 0.593 | 498, 0.584, 91% | 303, 0.584, 79% | +46.2% (+30%, +95%) | +39.0% | FAIL | pass/FAIL | pass |

**M0 frozen rule: does not transfer** (smallest Gcs-vs-threshold reduction +2.8%).

## M1 margin

| held-out | target ret | threshold: FV/h, ret | Gc: FV/h, ret, kept | Gcs: FV/h, ret, kept | Gcs vs threshold (95 % CI) | Gcs vs Gc | T1 | T2 thr/Gcs | T3 |
|---|---|---|---|---|---|---|---|---|---|
| em | 0.637 | 1004, 0.607 | 880, 0.648, 95% | 1084, 0.707, 100% | -8.2% (-12%, -3%) | -23.2% | pass | FAIL/pass | FAIL |
| ma | 0.512 | 476, 0.514 | 216, 0.411, 77% | 359, 0.507, 82% | +22.6% (+2%, +75%) | -66.6% | pass | pass/pass | pass |
| bw | 0.613 | 608, 0.601 | 568, 0.633, 96% | 338, 0.608, 82% | +43.0% (+28%, +91%) | +40.6% | pass | pass/pass | pass |

**M1 margin: does not transfer** (smallest Gcs-vs-threshold reduction -8.2%).

## M2 probability

| held-out | target ret | threshold: FV/h, ret | Gc: FV/h, ret, kept | Gcs: FV/h, ret, kept | Gcs vs threshold (95 % CI) | Gcs vs Gc | T1 | T2 thr/Gcs | T3 |
|---|---|---|---|---|---|---|---|---|---|
| em | 0.637 | 988, 0.598 | 162, 0.439, 69% | 709, 0.660, 90% | +27.1% (+7%, +64%) | -338.7% | pass | FAIL/pass | pass |
| ma | 0.512 | 450, 0.491 | 33, 0.324, 61% | 212, 0.437, 71% | +51.5% (+37%, +89%) | -538.7% | FAIL | FAIL/FAIL | pass |
| bw | 0.613 | 581, 0.593 | 77, 0.351, 69% | 60, 0.445, 65% | +89.4% (+86%, +99%) | +22.4% | FAIL | pass/FAIL | pass |

**M2 probability: does not transfer** (smallest Gcs-vs-threshold reduction +27.1%).

## Decision

**No method transfers** (decision rule 2): no fixed-cut-off Gcs design is claimed; the design falls back to threshold plus detector-quality deferral, with Gcs kept as an option.
