# Phase 1 design decision

Status: **decided 2026-10-07: v1.0 is threshold-only**, frozen as git tag
`v1.0-threshold`. Team decision recorded; **supervisor sign-off of this decision and of
`docs/intended_use.md` is still open.**

## 1. Mapping the verdict to a design

| Path | Design | Outcome |
|---|---|---|
| Gate wins on DS2 | Gcs as lead, *if* fixed cut-offs transfer to unseen noise | Verdict met; transfer failed (section 2) |
| Fallback | Threshold plus detector-quality (qSQI) deferral | Failed its pre-registered transfer test (section 2) |
| Threshold only | Robust at a fixed threshold | **Chosen for v1.0** |

## 2. Evidence

- **DS2, freeze-v1, frozen claim rule: gate wins.** Gcs vs raised threshold: 31.4 %
  fewer false V/h (95 % CI 22.8-40.9 %) at matched retention, with operating points
  matched on DS2 itself (`docs/ds2_verdict_freeze-v1.md`).
- **Q2 (secondary).** Gcs beats Gc by 22.5 % (CI 11.3-32.6 %) with matched settings,
  but the advantage turns negative on em and ma once cut-offs are fixed in advance.
- **Gate calibration, pre-registered: no method transfers**
  (`docs/calibration_plan.md`, `docs/calibration_results.md`). Gcs's coverage or its
  effect fails on at least one unseen noise type under every method, and raising
  the SVM threshold on calibration data makes retention drift on em.
- **qSQI deferral, pre-registered: no method passes**
  (`docs/qsqi_deferral_plan.md`, `docs/qsqi_deferral_results.md`). The a-priori rule
  (default threshold, qSQI < 0.8) holds coverage and retention on every unseen noise
  type, but cuts false V/h by only 7.4 % on baseline wander against a 20 % bar.
  Observed after the run: at the default threshold, retention held on all three
  noise types.

## 3. Decision: the v1.0 design

1. **Per beat:** the Robust SVM, with the weights from the freeze-v1 DS2 run
   (`models/v1.0_robust.json`), calls V when its decision value is above the default
   threshold, 0. The threshold is never tuned on external, pilot or own data.
2. **Per 10 s window:** *V suspected* (at least one V call), *no V*, or
   *insufficient* (fewer than 3 beats detected). There is **no signal-quality
   deferral**; the qSQI rule failed its pre-registered bar and is dropped from v1.0.
3. **Implementation:** `src/vgate/design.py`, frozen at `v1.0-threshold`. Any change
   is a new tagged version.
4. **Research options outside v1.0:** the Gcs gate and the qSQI rule. Neither may be
   shown to users as a reason for a decision.

### Reference performance (DS2, freeze-v1 run; for Phase 2 margins)

| DS2 data | False V/h (pooled) | Median record | V retention | Windows decided |
|---|---|---|---|---|
| Clean copies | 104 | 16 | 0.910 | 100 % |
| Noisy copies, all NSTDB types | 513 | 453 | 0.902 | 100 % |
| em / ma / bw | 755 / 490 / 294 | | 0.906 / 0.881 / 0.920 | 100 % |
| Noisy segments at 18 / 12 / 6 / 0 dB | 140 / 295 / 1257 / 2499 | | 0.907 / 0.916 / 0.898 / 0.814 | |

The beat-count rule never triggered on DS2: every window was decided. Six of 21 DS2
records carry most of the clean-signal false V calls (bundle-branch beats).

## 4. PRD v1.0 scope

**In scope**
- Single-lead ECG at 360 Hz from the ESP32-S3 / AD8232 strap. Classifier band-pass
  and Pan-Tompkins in C, matching the Python reference.
- The v1.0 per-beat and per-window decisions above.
- A reviewer screen per window: filtered ECG, beat markers, the SVM margin for each
  V flag, and the state. *Insufficient* is shown only for the beat-count reason.
- Replay of MIT-BIH clips through the same firmware, labelled as replay.

**Out of scope for v1.0**
- Any signal-quality deferral (qSQI, Gcs). SQIs may be displayed for review, but
  never as a decision.
- VF/VFL detection, paced rhythms, alarms, real-time clinical alerting.
- Any claim from the DS2 gate result for the device.

## 5. Consequences and open items

- **v1.0 is weak on noisy windows.** With no quality deferral, noise raises false V
  calls from about 104/h (clean) to about 513/h (NSTDB-noisy), and to about 2,500/h at
  0 dB. `docs/intended_use.md` says so.
- **Phase 2 must run the frozen design unchanged.** Margins are written before any
  external run (`docs/phase2_plan.md`).

| Open item | Needed from |
|---|---|
| Supervisor sign-off of this decision and `docs/intended_use.md` | supervisor |
| Push the `freeze-v1` and `v1.0-threshold` tags | team |
| Agree the Phase 2 margins before any external run | team |
