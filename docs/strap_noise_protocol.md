# Strap noise recording protocol (fresh data for the re-test)

**Purpose.** Record real wearable artefact from the team's AD8232 / ESP32-S3 strap,
playing the role NSTDB's em, ma and bw recordings played in the study: noise to be
mixed into clean MIT-BIH ECG at known SNRs. Settings fixed on DS1 are then re-tested
on noise they have never seen. The re-test plan (settings, pass criteria) must be
written and committed **before** any strap recording is mixed into ECG.

## 1. The heartbeat problem and the placement that avoids it

A chest-strap recording always contains the wearer's ECG. Mixed into MIT-BIH it would
add a second heartbeat, which corrupts beat detection and labels. NSTDB avoided this
by placing electrodes where the ECG is negligible. Do the same:

- **Signal electrodes (RA and LA inputs)** about 3-5 cm apart on the *same* upper arm,
  over the biceps. The heart's field is nearly equal at both, so the difference
  between them carries almost no ECG.
- **Reference electrode (RL input)** on the same arm near the elbow, or on the wrist.
- Use the strap's own electrodes, gel and cables, so contact behaviour matches the
  product.

Every recording is checked automatically (section 4). A recording in which more than
5 % of minutes show a regular heartbeat is refused.

## 2. Acquisition settings

- Sample the AD8232 output with a timer-driven ADC, ideally at **360 Hz**. Any steady
  rate of 250-1000 Hz is fine; ingest resamples to 360 Hz.
- Log raw ADC counts, one sample per row, to a CSV file (an optional first column of
  sample index is allowed). Record the true sampling rate.
- Note the board's own filters. Typical AD8232 breakouts high-pass around 0.5 Hz and
  low-pass around 40 Hz, so slow baseline wander is partly removed before the ADC.
  That matches what the product itself will see, but write the actual corner
  frequencies down.
- Absolute amplitude does not matter. The mixer scales each noise block to the
  target SNR from its own power, so no mV calibration is needed.

## 3. Sessions

At least **17 minutes per noise type per volunteer** (8 two-minute blocks plus
margin), and ideally two or more volunteers. Rest about 1 minute between activities;
the rests are kept (real recordings contain them).

| Type | Activities (repeat in turn) |
|---|---|
| **em** (electrode motion) | tug the leads gently; press and rock each electrode; swing the arm so the cable moves; walk with the cable loose |
| **ma** (muscle) | squeeze a grip ball; flex and extend the elbow; wall push-ups; hold a 2 kg weight with the arm extended |
| **bw** (baseline and movement) | slow deep breathing; twist the torso; walk; climb stairs |

Also record **2 minutes at rest** at the start of each session. The heartbeat check
should pass on it, which confirms the placement before activities start.

Name files `strap_<type>_<volunteer code>_<session>.csv`, for example
`strap_em_v1_s1.csv`. Use volunteer codes only: no names, no dates of birth.

## 4. Ingest and checks

```
python scripts/ingest_strap_noise.py strap_em_v1_s1.csv --fs 360 --type em --name strap_em_v1_s1
```

The script:
- resamples to 360 Hz and removes the mean;
- runs the heartbeat check: Pan-Tompkins on each minute, flagged when there are at
  least 30 detections per minute with RR variation under 15 %;
- reports length and the number of two-minute blocks;
- writes a WFDB record and a JSON summary to `data/raw/strap/` (git-ignored, like all
  data).

Refused recordings are re-recorded, not forced through. `--force` exists only for
inspecting a failure.

## 5. Consent and data handling

Volunteers are team members who agree in writing to wear the strap and do the
activities. Recordings contain only noise from an arm placement, no ECG. Raw files
stay off public repositories; only summaries and results are shared.
