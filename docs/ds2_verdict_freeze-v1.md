# vgate DS2 verdict - DS2, frozen tag freeze-v1

commit `004db108834ee3bfa82318da9ceaf8efce52490a`, 2026-10-07

## Verdict: **GATE WINS**

Claim rule: Gcs vs raised threshold on all 21 records, retention 0.9 x Robust default (0.812); gate wins if the reduction >= 20%, the CI lower bound > 0 and Gcs coverage >= 80% for every noise type (bw 87.3%, em 89.1%, ma 82.4%).

## Results (retention target 0.9)

| comparison | reduction | 95 % CI | false V/h | V retention | coverage |
|---|---|---|---|---|---|
| **Gcs vs raised threshold (deciding)** | +31.4% | [+22.8%, +40.9%] | 326.3 -> 223.7 | 0.814 -> 0.812 | 86.2% |
| Gc vs raised threshold | +11.5% | [-1.2%, +23.9%] | 326.3 -> 288.7 | 0.814 -> 0.812 | 87.0% |
| Gcs vs Gc | +22.5% | [+11.3%, +32.6%] | 288.7 -> 223.7 | 0.812 -> 0.812 | 86.2% |
| Robust (default) -> raised threshold | +36.4% | [+33.1%, +39.6%] | 512.9 -> 326.3 | 0.902 -> 0.814 | 100.0% |

Without clean-error records (105, 213, 219, 222, 228, 232; clean copy > 60 false V/h):

| comparison | reduction | 95 % CI | false V/h | V retention | coverage |
|---|---|---|---|---|---|
| Gcs vs raised threshold | +40.3% | [+29.5%, +49.7%] | 276.8 -> 165.1 | 0.809 -> 0.820 | 88.0% |
| Gcs vs Gc | +32.7% | [+25.3%, +39.6%] | 245.3 -> 165.1 | 0.803 -> 0.820 | 88.0% |

Per noise type (shared operating point):

| comparison | reduction | 95 % CI | false V/h | V retention | coverage |
|---|---|---|---|---|---|
| bw: Gcs vs raised threshold | +22.3% | [+10.1%, +34.7%] | 162.5 -> 126.2 | 0.840 -> 0.823 | 87.3% |
| em: Gcs vs raised threshold | +20.3% | [+12.2%, +28.7%] | 494.2 -> 394.0 | 0.814 -> 0.838 | 89.1% |
| ma: Gcs vs raised threshold | +53.2% | [+42.4%, +64.7%] | 322.0 -> 150.7 | 0.789 -> 0.775 | 82.4% |

Other retention targets:

| comparison | reduction | 95 % CI | false V/h | V retention | coverage |
|---|---|---|---|---|---|
| 0.8: Gcs vs raised threshold | +22.7% | [+8.3%, +37.9%] | 216.8 -> 167.5 | 0.729 -> 0.781 | 82.9% |
| 0.95: Gcs vs raised threshold | +19.4% | [+12.8%, +26.3%] | 406.1 -> 327.3 | 0.858 -> 0.857 | 91.4% |

Sensitivity: with record 202:

| comparison | reduction | 95 % CI | false V/h | V retention | coverage |
|---|---|---|---|---|---|
| Gcs vs raised threshold | +30.7% | [+21.9%, +39.8%] | 323.6 -> 224.3 | 0.814 -> 0.811 | 86.5% |

Robust false V/h on each record's clean copy: 100 0, 103 2, 105 507, 111 36, 113 12, 117 6, 121 32, 123 2, 200 10, 210 30, 212 2, 213 60, 214 6, 219 145, 221 0, 222 517, 228 139, 231 22, 232 629, 233 16, 234 4

---

## Reading the result (added after the run; the section above is the script's output, unedited)

The claim rule is met: Gcs cuts false V calls/hour by 31.4 % (95 % CI 22.8-40.9 %)
against a raised threshold at matched V retention (0.812 vs 0.814), keeping 82-89 %
of windows in each noise type. Limits that belong next to that number:

1. **Operating points were matched on DS2 itself**, by fixed rules that never look
   at false V calls (decision 1 in `docs/freeze_v1.md`). This tests whether the gate
   ranks windows better than a threshold does, not whether a cut-off fixed in
   advance transfers. In the DS1 pilot, cut-offs set on other noise types
   transferred poorly (Gcs kept 75-76 % of windows in two of three folds), so a
   deployed device still needs that problem solved.
2. **"Held-out noise" means held-out segments, not new noise types**: DS2 uses noise
   blocks 9-15 of em, ma and bw; the gates were trained on blocks 5-7 of the same
   three recordings.
3. **The SQIs carry the effect.** Confidence features alone (Gc) give +11.5 % with a
   CI that crosses zero (-1.2 % to +23.9 %); Gcs vs Gc at about the same deferral is
   +22.5 % (11.3-32.6 %).
4. **Secondary targets are weaker.** At 0.95 x retention the reduction is 19.4 %,
   just under the 20 % bar. At 0.8 the arms are not matched: the gate stopped at its
   20 % deferral cap with retention 0.781 against the threshold arm's 0.729.
5. **Clean-error records**: 6 of 21 DS2 records (105, 213, 219, 222, 228, 232; 213
   only just, at 60.3 false V/h against a 60 cut-off) already have many false V
   calls on clean signal. Without them the effect is larger (+40.3 %, 29.5-49.7 %).
   Adding record 202 changes little (+30.7 %).
6. **Absolute rates stay high**: about 224 false V/h with Gcs at this retention. The
   gate cuts noise-driven false calls, but the classifier's clean-signal precision
   remains the limiting factor for clinical use.

Reproduce: `git checkout freeze-v1 && python scripts/run_ds2.py` (the script refuses
a second run into the same results folder; move `results/ds2/freeze-v1/` aside
first). Models and window table: `results/ds2/freeze-v1/` (not in git).

## Deviations

Five Phase 0 checklist items were incomplete when DS2 ran; see "Deviations from the
Phase 0 checklist" in `docs/freeze_v1.md`. In particular, no DS2 confidence-interval
width was predicted from the pilot before the run.
