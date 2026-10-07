"""Export the three noise schedules per record (cycle offsets 0-2) to
configs/noise_schedules.json, and check them against the processed copies.

  python scripts/export_schedules.py

Post-freeze record (not part of freeze-v1): the schedules are generated
deterministically by noise.mixer.build_schedule from the committed configs; this file
writes them out with each segment's gain per noise type, and verifies that the
per-window SNRs stored by the frozen runs (results/cache) match them. Reads DS2
signals, so it is only for use after the DS2 run.
"""

from __future__ import annotations

import json

import numpy as np

from vgate import config, windows
from vgate.data import mitdb, nstdb
from vgate.noise import mixer
from vgate.pipeline import CACHE_DIR, CACHE_VERSION, Copy

OUT = config.CONFIG_DIR / "noise_schedules.json"


def main() -> None:
    sp, ns = config.splits(), config.pipeline()["noise_schedule"]
    noise = {k: nstdb.load_noise(k) for k in sp["noise"]["types"]}
    sets = {"train": mitdb.ds1_train(), "cal": mitdb.ds1_cal(), "test": mitdb.ds2(True)}
    out, checked, mismatched = {}, 0, []
    for split, recs in sets.items():
        blocks = sp["noise"][f"{split}_blocks"]
        for r in recs:
            rec = mitdb.load_record(r, allow_test=True)
            s_power = mixer.signal_power(rec.signal, rec.ann_sample[rec.ann_aami == "N"],
                                         rec.fs, ns["signal_power_qrs"])  # fmt: skip
            entry = {"split": split, "n_samples": len(rec.signal), "signal_power_mv2": s_power,
                     "schedules": {}}  # fmt: skip
            starts = windows.window_starts(len(rec.signal), rec.fs)
            win = config.pipeline()["window_s"] * rec.fs
            for off in ns["cycle_offsets"]:
                segs = mixer.build_schedule(len(rec.signal), rec.fs, blocks, off)
                for s in segs:
                    n = s["stop"] - s["start"]
                    s["gain"] = {
                        k: mixer.noise_scale(s_power, mixer.noise_power(
                            v[mixer.block_slice(s["block"], n, rec.fs)] -
                            v[mixer.block_slice(s["block"], n, rec.fs)].mean(), rec.fs),
                            s["snr_db"])
                        for k, v in noise.items()
                    }  # fmt: skip
                entry["schedules"][str(off)] = segs
                for kind in noise:
                    c = Copy(r, split, kind, off)
                    sub = "ds2" if split == "test" else ""
                    path = CACHE_DIR / f"v{CACHE_VERSION}" / sub / f"{c.name}.npz"
                    if not path.exists():
                        continue
                    with np.load(path) as z:
                        st, snr = z["starts"], z["snr_db"]
                    want = np.full(len(st), np.nan)
                    for i, s0 in enumerate(st):
                        for s in segs:
                            if s["start"] < s0 + win and s0 < s["stop"]:
                                want[i] = s["snr_db"]
                    checked += 1
                    if not np.array_equal(want, snr, equal_nan=True) or len(st) > len(starts):
                        mismatched.append(c.name)
            out[str(r)] = entry
    OUT.write_text(json.dumps(out, indent=1))
    print(f"wrote {OUT}: {len(out)} records x {len(ns['cycle_offsets'])} schedules")
    print(f"checked {checked} processed copies against the schedules: "
          f"{'all match' if not mismatched else f'MISMATCH {mismatched}'}")


if __name__ == "__main__":
    main()
