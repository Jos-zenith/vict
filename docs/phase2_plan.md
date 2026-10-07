# Phase 2 plan: external validity (pre-registration)

**Written and committed before any external data was downloaded or run.** The
margins in section 3 are a proposal: the team agrees or amends them, and commits the
agreed version, **before** the first external run. After that they do not change.

## 1. What is tested

The frozen v1.0 design, tag `v1.0-threshold` (`src/vgate/design.py`,
`models/v1.0_robust.json`), **unchanged**: no retraining, no threshold change, no
feature change. Only loaders and resampling are added for new data, and they must not
touch the design.

## 2. Datasets and processing

| Dataset | Records | Rate | Lead used | Notes |
|---|---|---|---|---|
| **INCART** (St Petersburg 12-lead Arrhythmia Database, PhysioNet `incartdb`) | 75 x 30 min, 32 patients | 257 Hz | II | Several records per patient: bootstrap resamples **patients** |
| **SVDB** (MIT-BIH Supraventricular Arrhythmia Database, `svdb`) | 78 x 30 min | 128 Hz | ECG1 | Lead is a modified limb lead similar to MLII; the low rate is part of the test |
| **Strap noise** (`docs/strap_noise_protocol.md`) | as recorded | resampled | n/a | Real wearable artefact, mixed into the clean records above |
| **Own data** (AD8232 strap with a reference Holter) | after ethics approval | | | Separate pre-registration once data exist |

Processing for INCART and SVDB is the same as DS2 had:
- Resample to 360 Hz (polyphase), scaling annotation samples by 360 / rate.
- AAMI mapping as for MIT-BIH. Records containing paced beats are excluded, and the
  exclusions are listed.
- Windows overlapping VF/VFL episodes are left out.
- One clean copy, plus noisy copies for em, ma and bw at cycle offsets 0-2, using
  NSTDB test blocks 9-15 and the same schedule. The schedules are written to a file
  before the run.

## 3. Pass margins (proposal; anchored to the DS2 reference in `docs/phase1_design_decision.md`)

For each external dataset, pooled over its records:

| # | Measure | DS2 reference | Margin |
|---|---|---|---|
| E0 | Beat detection Se and PPV, clean | 0.997 / 0.990 (DS1) | both >= 0.98 |
| E1 | V retention, clean | 0.910 | >= 0.85 |
| E2 | V retention, noisy (all NSTDB types) | 0.902 | >= 0.85 |
| E3 | False V/h, clean | 104 | <= 160 (1.5 x) |
| E4 | False V/h, noisy (all NSTDB types) | 513 | <= 770 (1.5 x) |
| E5 | Windows decided | 100 % | >= 99 % |

**Strap noise** (once recorded): mixed into the same clean records with the same
schedule. It passes if retention is >= 0.85 and false V/h is <= 1.5 x the same
records' NSTDB-noisy false V/h.

**Gate.** Phase 2 passes if every margin holds on every dataset. If any fails, the
design does not go on unchanged: the next step is retraining on real noise and a new
frozen version, as the Phase 2 gate says. Results are reported per dataset, per noise
type and per record, including every failure, whatever the outcome.

## 4. Stronger-classifier comparison (after the frozen-design run)

The conformal confidence gate is dropped: v1.0 has no gate.

- **Candidates.** (a) Gradient-boosted trees (`HistGradientBoostingClassifier`) on the
  same 14 beat features, class-balanced. (b) Optionally, a small 1-D CNN on beat
  segments; this needs PyTorch as a new dependency.
- **Training.** Exactly Robust's data (DS1-train clean and noisy copies), with
  hyperparameters chosen by record-grouped CV on DS1-train only. DS2 is not used.
- **Comparison.** On INCART and SVDB, clean and noisy. The primary measure is false
  V/h at matched V retention, where each classifier's threshold is set by the DS2
  rule: the highest threshold with retention >= 0.9 x that classifier's default
  retention. That rule never looks at false V calls. Each classifier's own default
  threshold is also reported. Bootstrap by patient (INCART) or record (SVDB);
  meaningful at >= 20 %.
- **Consequence.** A better classifier becomes a v1.1 candidate with its own freeze.
  It never changes the v1.0 result above.
