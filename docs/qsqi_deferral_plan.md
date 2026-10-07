# Phase 1 study: can the fallback design be frozen?

**Written and committed before any result was computed.** Script:
`scripts/run_qsqi_deferral.py`; results go to `docs/qsqi_deferral_results.md`.

## Question

The proposed v1.0 design (`docs/phase1_design_decision.md`) is the Robust classifier
at a fixed SVM threshold θ plus a detector-quality deferral. A window is *data quality
insufficient* (no V calls) when qSQI < q* (Pan-Tompkins and Mexican-hat disagree) or
fewer than 3 beats are detected. The calibration study showed that fixed settings can
drift on unseen noise, including the threshold's retention. Do θ and q*, fixed in
advance, hold on a noise type and a record never seen?

## Data and folds (DS1 only; DS2 is never read)

The same as `docs/calibration_plan.md`. For each held-out noise type h and DS1-cal
record r (18 folds):

- **Robust_h**: trained on DS1-train clean + noisy copies of the other two types.
- **Calibration set**: other DS1-cal records, other two noise types (noisy copies).
- **Test set**: record r, noise type h, all three cycle offsets.

Results for each noise type are pooled over its six record folds.

## Methods

| Method | SVM threshold θ | qSQI cut-off q* | Settings fitted on the calibration set |
|---|---|---|---|
| **D0 a priori** | default (0) | 0.8 | none |
| **D1 calibrated deferral** | default (0) | the largest q* at which every calibration noise type keeps >= 85 % of windows | q* |
| **D2 calibrated threshold** | the highest θ at which calibration retention, with the D0 deferral applied, is >= 0.9 x Robust's default retention | 0.8 | θ |

All methods also defer windows with fewer than 3 detected beats. q* = 0.8 is a
conventional detector-agreement level, chosen a priori rather than from these data.

## Pass criteria (each held-out noise type, pooled over its records)

- **T1 coverage**: >= 80 % of windows kept.
- **T2 retention**: V retention >= 0.9 x the test set's Robust default retention, minus 0.02.
- **T3 effect**: false V/h at least 20 % lower than the same θ without deferral.
- **T4 better than chance**: that reduction is larger than the share of windows deferred.

A method can be frozen if T1-T4 hold for all three noise types. Also reported, but
not used to pass or fail: how the deferrals split between the qSQI and beat-count
reasons, and the raised-threshold and Gcs arms calibrated as in method M0 of the
calibration study.

## Decision rule (fixed now)

1. If any method passes, the fallback design is freezable. Use the first passing
   method in the order D0, D1, D2 (fewest settings fitted to data first).
2. If none passes, the fallback cannot be frozen with fixed settings. The team then
   chooses between threshold-only (no deferral, with retention drift documented) and
   a new pre-registered study of adaptive calibration.
3. Either way the selection is made on DS1, so it is not a claim until the strap-noise
   re-test.
