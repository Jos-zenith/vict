# Phase 1 calibration study: do fixed cut-offs transfer to an unseen noise type?

**Written and committed before any result was computed.** Script:
`scripts/run_calibration.py`; results go to `docs/calibration_results.md`.

## Question

The freeze-v1 DS2 run matched retention on DS2 itself. A device needs settings fixed in
advance. In the DS1 pilot, cut-offs set on two noise types and applied to the third
broke the coverage rule (Gcs kept 75-76 % of windows) and lost the Gcs-over-Gc
advantage (-8.5 %). This study asks whether a calibration step can fix both arms'
settings in advance so that they hold on a noise type, and a record, never seen.

## Data and folds (DS1 only; DS2 is never read)

For each held-out noise type h in {em, ma, bw} and each DS1-cal record r (18 folds):

- **Robust_h**: SVM trained on DS1-train clean + noisy copies of the two other noise
  types, with Base's C (as in the pilot).
- **Calibration set**: DS1-cal records other than r, noisy copies of the two other
  noise types. Gc and Gcs are trained on it (clean-paired risk labels) and every
  setting is fixed on it.
- **Test set**: record r, noisy copies of type h (all three cycle offsets).

Results for each noise type are pooled over its six record folds. Each test window is
therefore scored by settings fixed without its noise type and without its record.

## Methods (fixed cut-offs; retention target rho = 0.9 x Robust's default retention)

Both arms are calibrated the same way within a method.

| Method | Raised-threshold arm | Gated arms (Gc, Gcs; SVM at default) |
|---|---|---|
| **M0 frozen rule** | highest SVM threshold with calibration retention >= rho x default | defer riskiest windows while calibration retention >= target, at most 20 % of windows of each calibration noise type |
| **M1 margin** | as M0 with rho = 0.92 | as M0 with rho = 0.92 and at most 15 % per noise type |
| **M2 probability** | as M0 | defer when the gate's predicted P(risky) >= 0.5 |

## Pass criteria (each held-out noise type, pooled over its records)

- **T1 coverage**: Gcs keeps >= 80 % of windows.
- **T2 retention**: both arms' V retention >= the test set's own 0.9 x default
  retention minus 0.02.
- **T3 effect**: Gcs has fewer false V/h than the raised-threshold arm.

A method **transfers** if T1-T3 hold for all three noise types. Gcs vs Gc and Gc vs
the threshold arm are reported, not used to pass or fail.

## Decision rule (fixed now)

1. If one or more methods transfer, the lead calibration is the one with the largest
   *minimum* Gcs-vs-threshold reduction across the three noise types. Ties go to
   M0, then M1, then M2 (simplest first).
2. If none transfers, no fixed-cut-off Gcs design is claimed. The Phase 1 design then
   falls back to "threshold plus detector-quality deferral", with Gcs kept as an
   option pending a new calibration approach.
3. Whatever is chosen here is selected on DS1 and is therefore not a claim. The
   claim needs the fresh-data re-test (Phase 1 checklist item 3).
