# Phase 1 design decision (proposed, for sign-off)

Status: **proposed**. It takes effect when the team signs it off together with
`docs/intended_use.md`.

## 1. Mapping the verdict to a design

| DS2 verdict | Design | Applies? |
|---|---|---|
| Gate wins | Gcs is the lead design, *if* a calibration with fixed cut-offs transfers to unseen noise types | **Verdict met; transfer condition not met** (section 3) |
| Inconclusive | Ship the threshold with a detector-quality deferral; keep gating as an option | **Applied as the fallback** (decision rule 2 of the pre-registered study) |
| Threshold wins | Ship the threshold only | no |

## 2. Evidence

- **Primary (freeze-v1, DS2, frozen claim rule): gate wins.** Gcs vs raised
  threshold: 31.4 % fewer false V/h (95 % CI 22.8-40.9 %) at matched V retention
  (0.812 vs 0.814), coverage 82-89 % per noise type. Operating points were matched
  on DS2 itself (`docs/ds2_verdict_freeze-v1.md`).
- **Q2, secondary (not part of the frozen claim rule).** Gcs beats Gc by 22.5 %
  (CI 11.3-32.6 %) while keeping 86.2 % of windows against 87.0 %; Gc alone vs the
  raised threshold is +11.5 % (CI -1.2 to +23.9 %), not significant. Per noise type,
  Gcs over Gc: bw +33.5 %, ma +33.2 %, em +12.6 %. The per-type rows are not exactly
  retention-matched (in bw Gcs keeps 87.3 % against 90.8 %).
- **Calibration transfer, pre-registered (`docs/calibration_plan.md`, committed
  before the run; results in `docs/calibration_results.md`): no method transfers.**
  With every setting fixed without the test noise type and record (DS1 only):
  - *M0, the frozen rule*: Gcs keeps 76 % (ma) and 79 % (bw) of windows, under the
    80 % rule.
  - *M1, with margins*: passes on ma and bw, but on em Gcs defers nothing and
    ends with more false V/h than the threshold arm (-8.2 %).
  - *M2, a fixed P(risky) cut*: defers too much (65-71 % kept on ma and bw).
  - Gcs over Gc turns negative on em and ma under every method, so **the Q2
    advantage does not hold with fixed cut-offs.**
  - The raised-threshold arm's retention also drifts on em (0.598-0.607 against a
    0.617 floor), so fixed settings are a problem for the fallback too, not only
    for the gate.

## 3. Decision (proposed)

1. **Product design for v1.0: Robust classifier at a fixed threshold, plus a
   detector-quality deferral**, with three window states: *V suspected*, *no V*,
   *data quality insufficient*.
2. **Gcs is kept as an option, not as the shipped design or a claim.** It returns
   to lead only after (a) a calibration that passes a pre-registered transfer test
   and (b) a re-test of the fixed cut-offs on fresh data.
3. **Q2 is recorded as secondary evidence only.** It supports the SQIs when settings
   are matched to the data, not with fixed settings.
4. **Detector-quality deferral rule**: defer a window when Pan-Tompkins and the
   Mexican-hat detector disagree (qSQI below a cut-off) or fewer than 3 beats are
   detected (`[windowing] min_beats`). The qSQI cut-off is not chosen yet. It must
   be set by a pre-registered transfer test like the one in section 2, including a
   retention check for the threshold itself.

## 4. PRD v1.0 scope (proposal)

**In scope**
- Single-lead ECG at 360 Hz from the ESP32-S3 strap. Classifier band-pass,
  Pan-Tompkins and Mexican-hat in C, matching the Python reference.
- Robust SVM V/non-V per beat at a fixed threshold, and a decision per 10 s window
  in the three states above.
- A reviewer screen per window: filtered ECG, beat markers, the four SQIs, and the
  SVM margin for each V flag.
- Replay of MIT-BIH clips through the same firmware, labelled as replay.

**Out of scope for v1.0**
- Gcs gating as a shipped feature (kept behind a flag for research).
- VF/VFL detection, paced rhythms, any alarm or real-time clinical alerting.
- Any claim from the gate result beyond the DS2 study conditions.

## 5. Open items before sign-off

| Item | Needed from |
|---|---|
| Accept the fallback design (section 3.1) instead of Gcs as lead | team |
| Fresh data for re-testing fixed settings. Options: noise recorded from the team's own strap (motion, cough, loose electrode) mixed into MIT-BIH; or an external ECG database such as INCART, resampled to 360 Hz | team |
| Pre-registered test for the qSQI deferral cut-off and the threshold's retention transfer | engineering (next study) |
| PRD v1.0 updated to section 4 | doc owner |
| Sign-off of this decision and `docs/intended_use.md` | supervisor and team |
