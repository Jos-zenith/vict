# vgate

**vgate** is a research proof of concept for detecting ventricular ectopic (V) beats
in noisy, single-lead ECG. It tests whether signal-quality features can help a
classifier defer risky 10-second windows and reduce false V calls while preserving
V-beat retention.

The Python pipeline uses MIT-BIH Arrhythmia Database recordings and adds noise from
the MIT-BIH Noise Stress Test Database (NSTDB). DS1 is used for development; DS2 is
reserved for a single, frozen evaluation. This is not a medical device and is not
for diagnosis, screening, or treatment decisions.

## Result

In the frozen DS2 evaluation, the signal-quality gate reduced false V calls by 31.4%
relative to a raised classifier threshold at similar V retention (95% CI: 22.8–40.9%).
This is an offline result on MIT-BIH records with NSTDB noise—not evidence of
performance on real wearable recordings or new noise types. Operating points were
matched on DS2, so the result does not establish a deployable cutoff.

See [the full DS2 report](docs/ds2_verdict_freeze-v1.md) and
[intended-use statement](docs/intended_use.md) for results, limitations, and protocol.

## Quick start

Requires Python 3.11 or newer. In Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python scripts/download_data.py
pytest
```

The download script fetches MIT-BIH and NSTDB into `data/raw/` (about 100 MB).
Without the datasets, data-dependent tests are skipped.

Run the development checks and DS1 pilot:

```powershell
python scripts/check_splits.py
python scripts/check_detector.py
python scripts/check_base.py
python scripts/run_pilot.py --record 114
python scripts/run_pilot.py
```

The single-record command exercises the full pipeline on one DS1 calibration
record. The full pilot evaluates held-out noise folds and writes results under
`results/pilot/`. Processed-record caches are stored in `results/cache/`.

## Frozen DS2 evaluation

The real DS2 run is intentionally guarded: it only runs from a clean `freeze-*`
Git tag and refuses a second run into the same results directory. Do not run it
from the development branch. The frozen evaluation and its protocol are documented
in [`docs/ds2_verdict_freeze-v1.md`](docs/ds2_verdict_freeze-v1.md).

To exercise the DS2 pipeline without using DS2 data, run:

```powershell
python scripts/run_ds2.py --dry-run
```

## Project structure

- `src/vgate/` — data access, filtering, beat detectors, noise mixing, features,
  classifiers, signal-quality gates, and evaluation.
- `configs/` — fixed record splits and pipeline parameters.
- `scripts/` — downloads, validation checks, pilots, and evaluation utilities.
- `tests/` — unit and data-dependent tests.
- `c/` — portable C signal-processing core and tests.
- `firmware/` — ESP32-S3 firmware project.
- `docs/` — study protocol, intended use, and reports.

For the optional C core, build and run its tests with CMake:

```powershell
cmake -S c -B c/build
cmake --build c/build
ctest --test-dir c/build
```
