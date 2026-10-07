# vgate

Detects **ventricular ectopic (V) beats** in noisy, single-lead ECG from a wearable
chest strap (AD8232 front end, ESP32-S3). This is a research proof of concept, run as a
pre-registered study. **It is not a medical device.**

**Status:** v1.0 is frozen as the threshold-only design (tag `v1.0-threshold`).
It has been validated offline on MIT-BIH only. Phase 2 (external datasets and real
strap noise) is pre-registered and has not been run yet. The C core and firmware are
partly built.

---

## Data provenance

| Source | Real or synthetic | Role |
|---|---|---|
| **MIT-BIH Arrhythmia DB** (PhysioNet `mitdb`): 48 × 30 min ambulatory recordings, 47 adults, 360 Hz, beats annotated by cardiologists | **Real** clinical ECG, recorded in 1975–79 and replayed offline | All training and testing |
| **MIT-BIH Noise Stress Test DB** (`nstdb`): electrode motion (`em`), muscle (`ma`) and baseline wander (`bw`) | Noise is **real** (recorded from volunteers). The **mixing is synthetic**: it is added to clean ECG in software at 18/12/6/0 dB SNR | Noise robustness |
| **Strap noise** (`docs/strap_noise_protocol.md`) | Real, from our own hardware | **Not recorded yet** |
| **Own ECG with a reference Holter** | Real | Waiting for ethics approval (`docs/ethics_application_draft.md`) |

No data is generated from scratch. No live or streaming data has been used so far.

**Split:** the inter-patient split of de Chazal et al. (2004). There are 22 DS1
records (16 for training and 6 for calibration) and 21 DS2 records, used for one
frozen test. Record 202 is excluded because it comes from the same subject as 201.
The four paced records are excluded. V means AAMI class V = {V, E}. DS1 has
3,323 + 465 V beats and DS2 has 3,202. Noise uses separate blocks: 1–4 for training,
5–7 for calibration and 9–15 for testing.

## Pipeline (360 Hz, MLII lead)

1. **Band-pass** at 0.5–40 Hz (4th-order biquads, float32).
2. **QRS detection** with Pan-Tompkins redesigned for 360 Hz (5–15 Hz band,
   150 ms integrator, 200 ms refractory period, search-back). It works sample by
   sample, so the C port can be a line-for-line translation.
3. **14 features per beat:** RR before and after, the mean of the last 10 RR, two
   prematurity ratios, QRS width, R and S amplitude, and six db4 wavelet band
   energies over −250…+450 ms.
4. **Robust linear SVM** (V vs non-V, C = 0.001). It is trained on DS1-train, both
   clean and NSTDB-noisy copies. A beat is called V when its decision value is
   above 0.
5. **Per 10 s window:** `V suspected` (at least one V call), `no V`, or
   `insufficient` (fewer than 3 beats).

**Model:** `models/v1.0_robust.json` holds real weights trained on real ECG: the
feature mean and scale, the coefficients and the intercept. Inference is one dot
product per beat.

## Results: v1.0 on DS2 (frozen, default threshold)

| DS2 condition | V retention | False V/h (pooled) |
|---|---|---|
| Clean | 0.910 | **104** (median record: 16) |
| NSTDB-noisy, all types | 0.902 | **513** |
| em / ma / bw | 0.906 / 0.881 / 0.920 | 755 / 490 / 294 |
| 18 / 12 / 6 / 0 dB | 0.907 / 0.916 / 0.898 / 0.814 | 140 / 295 / 1,257 / 2,499 |

- Beat detection on clean DS1: sensitivity 99.7 %, positive predictivity 99.0 %.
- Every window was decided; the fewer-than-3-beats rule never triggered.
- Six of the 21 DS2 records (105, 213, 219, 222, 228 and 232) cause most of the
  clean-signal false calls. These are mainly bundle-branch-block beats.

## What was tried and dropped

| Study | Result | Outcome |
|---|---|---|
| **Signal-quality gate (Gcs)**, frozen DS2 test | 31.4 % fewer false V/h than a raised threshold at matched retention (95 % CI 22.8–40.9 %) | The claim rule was met, but operating points were matched on DS2 itself |
| **Gate calibration** (pre-registered, DS1) | Cut-offs fixed in advance did not transfer to unseen noise types | **No method transfers** |
| **Detector-quality (qSQI) deferral** (pre-registered, DS1) | Only a 7.4 % reduction on `bw`, against a 20 % bar | **No method passes** |

The gate ranks noisy windows well, but no fixed cut-off survived unseen noise.
v1.0 therefore has **no signal-quality deferral**. Signal-quality indices (SQIs) may
be shown to a reviewer, but never used as a decision.

## Real-time readiness

| Component | State |
|---|---|
| Pan-Tompkins (Python) | Works sample by sample, ready to port |
| C core (`c/`) | Only the biquad band-pass exists. It is bit-identical to Python on MIT-BIH 119 and on synthetic test vectors |
| Detector, features and SVM in C | Not started |
| ESP32-S3 firmware (`firmware/`) | Planned only. The plan is an ESP-IDF project with the C core as a component, reading the AD8232 through an ADS1115 every 2.78 ms (360 Hz) |
| Acceptance targets | Firmware output matches Python within 1e-4, and each window takes under 2.5 s |

**Built-in latency:** a beat can be classified only after the next R peak (for RR
after) and about 450 ms of signal after it (for the wavelet span). A window is
therefore decided about one beat after it ends, with a 2 s timeout.

## Limitations

- All noise so far is NSTDB mixed in software. Performance on real wearable artefact
  and on other databases is unknown; finding it out is Phase 2's job.
- With no quality deferral, noisy windows produce many false V calls.
- The training data covers adults from MIT-BIH only. The system is not for paced
  rhythms, children, or VF/VT/asystole.
- v1.0 must not be retrained or re-thresholded on external or own data. Any change
  becomes a new frozen version.

## Phase 2 (pre-registered, not yet run)

The frozen v1.0 runs **unchanged** on INCART (257 Hz) and SVDB (128 Hz), both
resampled to 360 Hz, and then on real strap noise. It passes only if every margin
holds on every dataset:

- detection sensitivity and positive predictivity ≥ 0.98
- V retention ≥ 0.85, both clean and noisy
- false V/h no more than 1.5 × the DS2 rate (≤ 160 clean, ≤ 770 noisy)
- windows decided ≥ 99 %

A gradient-boosted classifier and an optional 1-D CNN will be compared afterwards as
candidates for v1.1.

## Intended use

Supervised research and teaching only. Output is reviewed by a trained person
alongside the raw ECG. V detection is demonstrated by replaying MIT-BIH, always
labelled as replay. Live use on a volunteer shows beat detection only. Not for
diagnosis, screening, alarms or real-time clinical monitoring, and not cleared by any
regulator.

## Documents

| Topic | File |
|---|---|
| Intended use (awaiting sign-off) | `docs/intended_use.md` |
| v1.0 design decision | `docs/phase1_design_decision.md` |
| DS2 verdict and freeze record | `docs/ds2_verdict_freeze-v1.md`, `docs/freeze_v1.md` |
| Pre-registered studies | `docs/calibration_*.md`, `docs/qsqi_deferral_*.md` |
| Phase 2 plan, strap protocol, ethics | `docs/phase2_plan.md`, `docs/strap_noise_protocol.md`, `docs/ethics_application_draft.md` |

**Code layout:** `src/vgate/` (Python reference), `c/` (portable C core),
`firmware/` (ESP32-S3), `configs/` (splits and parameters, fixed before the freeze),
`models/` (frozen weights).
