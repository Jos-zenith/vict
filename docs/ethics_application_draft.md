# Ethics application: draft content

Draft text for the institution's research ethics form. Sections marked **[TBD]** need
institution-specific details. This is not the form itself.

## Title
Wearable single-lead ECG recordings from healthy adult volunteers, alongside a
reference Holter monitor, for testing a ventricular-beat detection prototype.

## Background and aims
The project has built a prototype that detects heartbeats and flags ventricular
ectopic beats in single-lead ECG. It has been tested only on public databases with
noise added in software. This study records (1) real movement and muscle noise from
the prototype strap, and (2) short ambulatory ECG from the strap worn alongside a
standard Holter. The aim is to measure how well the prototype's beat detection and
false-alarm rate hold up on real wearable recordings. **No diagnosis is made, and no
result is returned to participants as a health finding.**

## Participants
- 10-20 healthy adult volunteers (18 or over), recruited from students and staff by
  notice; no payment **[TBD: institution policy]**.
- Exclusions: pacemaker or other implanted electronic device; known heart condition;
  pregnancy; skin allergy to ECG electrode gel or adhesive; broken skin at electrode
  sites.
- Participation is voluntary, with written informed consent and withdrawal at any
  time without giving a reason. Data are deleted on request until analysis is
  complete **[TBD: date]**.

## Procedures
1. **Noise session (about 1 hour, lab):** adhesive electrodes on the upper arm, as in
   `docs/strap_noise_protocol.md`. The participant does simple activities (arm
   movement, grip squeezes, walking, deep breathing, stairs) in blocks of a few
   minutes, with rests.
2. **Ambulatory session (up to 24 h):** the prototype chest strap and a reference
   Holter **[TBD: which device, provided by whom]** worn at the same time during
   normal daily life, avoiding water. A diary records activities and times.

## Risks and how they are managed
- **Skin irritation** from adhesive or gel: hypoallergenic electrodes; skin checked at
  removal; stop at any discomfort.
- **Electrical safety:** the prototype is battery-powered only (no mains connection
  during use) and uses an AD8232 front end with low supply voltage; it is never worn
  while charging. **[TBD: technical safety sign-off by the department]**
- **Incidental findings:** the prototype gives no clinical output. Reference Holter
  recordings are reviewed by **[TBD: named clinician]**. If they show a possibly
  significant abnormality, the participant is told and advised to see their GP. This
  is explained in the consent form, and participants can choose not to take part.
- **Burden:** wearing devices for up to 24 h; participants may stop at any time.

## Data handling
- Each participant gets a code (for example v1); the key linking codes to names is
  kept separately by **[TBD: data custodian]** and destroyed at **[TBD]**.
- Recordings hold ECG and noise signals only: no names, no dates of birth, no images.
- Storage on encrypted institutional storage **[TBD]**; never on public
  repositories. Only summaries and anonymised results are published.
- Retention **[TBD: institution policy, for example 5 years]**, then deletion.

## Documents to attach [TBD]
Participant information sheet, consent form, recruitment notice, device technical
description and safety assessment, Holter reviewer agreement.
