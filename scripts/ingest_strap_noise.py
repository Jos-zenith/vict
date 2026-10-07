"""Ingest a strap noise recording (docs/strap_noise_protocol.md) into data/raw/strap/.

  python scripts/ingest_strap_noise.py rec.csv --fs 500 --type em --name strap_em_v1

The CSV holds one sample per row (ADC counts); with several columns, --column picks
one (default: the last). The recording is resampled to 360 Hz, checked for the
volunteer's heartbeat, and written as a WFDB record. A recording with more than 5 %
of contaminated minutes is refused unless --force is given.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import wfdb

from vgate import config
from vgate.noise.strap import heartbeat_check, to_pipeline_rate

OUT_DIR = config.DATA_DIR / "strap"
MAX_CONTAMINATED = 0.05


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--fs", type=float, required=True, help="sampling rate of the recording")
    ap.add_argument("--type", choices=("em", "ma", "bw"), required=True)
    ap.add_argument("--name", required=True, help="record name, e.g. strap_em_v1")
    ap.add_argument("--column", type=int, default=-1)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    raw = np.loadtxt(a.csv, delimiter=",", ndmin=2)[:, a.column]
    fs = config.pipeline()["fs"]
    x = to_pipeline_rate(raw, a.fs)
    check = heartbeat_check(x, fs)
    block = config.splits()["noise"]["block_s"] * fs
    print(f"{a.name}: {len(raw)} samples at {a.fs:g} Hz -> {len(x)} at {fs} Hz "
          f"({len(x) / fs / 60:.1f} min, {len(x) // block} two-minute blocks)")  # fmt: skip
    print(f"heartbeat check: {sum(check['chunks'])} of {len(check['chunks'])} minutes look "
          f"like ECG ({check['contaminated_fraction']:.0%})")  # fmt: skip
    if check["contaminated_fraction"] > MAX_CONTAMINATED and not a.force:
        raise SystemExit(
            "Refused: the recording contains the volunteer's heartbeat. Re-record "
            "with the electrode placement in the protocol, or pass --force."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scale = np.max(np.abs(x)) or 1.0  # arbitrary units; the mixer sets the gain from SNR
    wfdb.wrsamp(a.name, fs=fs, units=["au"], sig_name=[f"strap_{a.type}"],
                p_signal=(x / scale)[:, None], fmt=["16"], write_dir=str(OUT_DIR),
                comments=[f"type {a.type}; source {a.csv} at {a.fs:g} Hz"])  # fmt: skip
    meta = {"type": a.type, "source": a.csv, "fs_in": a.fs, "heartbeat_check": check}
    (OUT_DIR / f"{a.name}.json").write_text(json.dumps(meta, indent=1))
    print(f"wrote {OUT_DIR / a.name}.hea/.dat")


if __name__ == "__main__":
    main()
