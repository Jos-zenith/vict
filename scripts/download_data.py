"""Download MIT-BIH Arrhythmia (mitdb) and Noise Stress Test (nstdb) into data/raw.

Usage: python scripts/download_data.py
"""

from __future__ import annotations

import wfdb

from vgate import config


def main() -> None:
    for db in ("mitdb", "nstdb"):
        out = config.DATA_DIR / db
        out.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {db} -> {out}")
        wfdb.dl_database(db, dl_dir=str(out))
    print("Done.")


if __name__ == "__main__":
    main()
