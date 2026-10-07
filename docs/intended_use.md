# vgate v1.0: intended-use statement (proposed, for sign-off)

## What it is
A single-lead ECG proof-of-concept: a chest strap with an ESP32-S3 records one ECG
lead at 360 Hz, and firmware labels every 10-second window as **V suspected**
(at least one ventricular ectopic beat), **no V**, or **data quality insufficient**.
For each window it also shows the filtered ECG, the detected beats, four signal-quality
indices, and the classifier's margin for each V flag.

## Intended use
To show, in a supervised research and teaching setting, that withholding a decision
when signal quality is poor is a workable way to limit false ventricular-beat calls
in noisy wearable ECG. Recordings and results are **for review by a trained person
alongside the raw ECG**. The device's labels are an aid to that review, not a
finding.

## Intended users and setting
Project team, supervisors and assessors, in lab and demonstration use. Live use is
limited to showing the *data quality insufficient* state on a healthy volunteer
(moving, coughing, loosening an electrode). V detection is demonstrated by replaying
MIT-BIH recordings through the same firmware, and is always labelled as replay.

## Not intended for
- Diagnosis, treatment decisions, or screening of patients.
- Alarms or real-time monitoring of any arrhythmia, including VF, VT and asystole.
  VF/VFL episodes are outside what the device scores.
- People with pacemakers (paced recordings were excluded from all data), children,
  or any population outside adult MIT-BIH-like recordings.
- Unsupervised use, or use by people without ECG training to interpret its output.

## Basis and known performance
- **Data**: the classifier and quality indices were developed on the MIT-BIH
  Arrhythmia Database, inter-patient split (DS1 for development, DS2 for one frozen
  test), with noise from the MIT-BIH Noise Stress Test Database added in software.
  No recordings from the strap itself have been evaluated yet.
- **Beat detection** on clean DS1: sensitivity 99.7 %, positive predictivity 99.0 %.
- **V calls on noisy DS2 data** (shipped design, fixed threshold, no gate): at a
  V-beat retention of about 81 %, about **326 false V calls per hour**. That is the
  main reason this is a supervised research use.
- **Quality gate (research option, not shipped)**: in the frozen DS2 study an
  SQI-based gate removed 31 % of false V calls at matched retention (95 % CI 23-41 %).
  Fixed gate settings did not transfer to unseen noise types in a pre-registered
  study, so this result is **not claimed for the device**.

## Known limitations
- Settings fixed in advance drift on unseen noise: V retention and the deferral rate
  change with the kind of noise.
- Some recordings produce many false V calls even on clean signal (for example
  bundle-branch-block beats); neither the threshold nor the gate removes these.
- The noise was synthetic (NSTDB recordings mixed into clean ECG), not real
  wearable motion artefact.

## Regulatory status
Not a medical device. Not cleared or approved for clinical use by any regulator.
Every recording or screen shown outside the team must carry that statement.

*Sign-off: ______________________ (supervisor) · ______________________ (team) · date ________*
