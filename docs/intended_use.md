# vgate v1.0: intended-use statement (for supervisor sign-off)

## What it is
A single-lead ECG proof-of-concept: a chest strap (AD8232 front end, ESP32-S3) records
one ECG lead at 360 Hz, and firmware labels each 10-second window **V suspected** (at
least one beat classified as a ventricular ectopic beat), **no V**, or
**insufficient** (fewer than 3 beats detected). Each window is shown with its
filtered ECG, the detected beats, and the classifier's margin for each V flag.

## Intended use
To demonstrate, in a supervised research and teaching setting, beat detection and
ventricular-beat classification on wearable single-lead ECG. Results are **for review
by a trained person alongside the raw ECG**. The device's labels are an aid to that
review, not a finding.

## Intended users and setting
Project team, supervisors and assessors, in lab and demonstration use. V detection
is demonstrated by replaying MIT-BIH recordings through the same firmware, always
labelled as replay. Live use on a volunteer shows beat detection only.

## Not intended for
- Diagnosis, treatment decisions, or screening of patients.
- Alarms or real-time monitoring of any arrhythmia, including VF, VT and asystole;
  VF/VFL episodes are outside what the device scores.
- People with pacemakers (paced recordings were excluded from all data), children, or
  populations unlike the adult MIT-BIH recordings.
- Unsupervised use, or use by people without ECG training to interpret its output.

## Basis and known performance
- **Data**: developed on the MIT-BIH Arrhythmia Database, inter-patient split (DS1 for
  development, DS2 for one frozen test), with noise from the MIT-BIH Noise Stress
  Test Database added in software. No strap recordings have been evaluated yet.
- **Beat detection**, clean DS1: sensitivity 99.7 %, positive predictivity 99.0 %.
- **V classification on DS2** (this design: fixed default threshold): V-beat
  retention 0.91 on clean signal and 0.90 with noise. False V calls: about **104 per
  hour on clean signal** (median record 16/h), rising to about **513/h with noise**
  and about **2,500/h in the noisiest (0 dB) segments**.

## Known limitations
- **No signal-quality deferral.** v1.0 decides every window that has 3 or more beats,
  however noisy; on DS2 that was every window. Noisy windows therefore produce many
  false V calls, and a reviewer must judge signal quality from the ECG trace.
  Quality-based deferral (an SQI gate, a detector-agreement rule) was studied, but
  its fixed settings did not transfer to unseen noise, so it is not part of v1.0.
- A few recordings produce many false V calls even on clean signal (for example
  bundle-branch-block beats).
- The noise was synthetic (NSTDB recordings mixed into clean ECG), not real wearable
  artefact. Performance on the strap and on other ECG databases is the subject of
  Phase 2 and is not known yet.

## Regulatory status
Not a medical device. Not cleared or approved for clinical use by any regulator.
Every recording or screen shown outside the team must carry that statement.

*Sign-off: ______________________ (supervisor) · ______________________ (team) · date ________*
