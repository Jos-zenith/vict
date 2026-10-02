"""Recount V beats per split and compare with configs/splits.toml.

DS1 only by default. `--ds2` reads DS2 reference labels for counting (no model is
run); use it once to confirm the published table, not during development.
"""

from __future__ import annotations

import argparse

from vgate import config
from vgate.data import mitdb


def v_count(records: list[int], allow_test: bool = False) -> int:
    return sum(
        int((mitdb.load_record(r, allow_test=allow_test).ann_aami == "V").sum()) for r in records
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ds2", action="store_true")
    args = ap.parse_args()

    expected = config.splits()["expected_v_beats"]
    sets = {"ds1_train": mitdb.ds1_train(), "ds1_cal": mitdb.ds1_cal()}
    if args.ds2:
        sets["ds2_test"] = mitdb.ds2()

    ok = True
    for name, recs in sets.items():
        n = v_count(recs, allow_test=name == "ds2_test")
        status = "OK" if n == expected[name] else "MISMATCH"
        ok &= status == "OK"
        print(f"{name:10s} {len(recs):2d} records  V={n:5d}  "
              f"expected {expected[name]:5d}  {status}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
