"""MIT-BIH Arrhythmia Database access with split guards.

DS2 is the held-out test set and is run once from the frozen tag. Loading a DS2
record requires ``allow_test=True`` so it cannot happen by accident during
development.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import wfdb

from vgate import config
from vgate.data.aami import aami_class

MITDB_DIR = config.DATA_DIR / "mitdb"


class TestSetAccessError(RuntimeError):
    pass


def ds1_train() -> list[int]:
    return list(config.splits()["ds1"]["train"])


def ds1_cal() -> list[int]:
    return list(config.splits()["ds1"]["cal"])


def ds1() -> list[int]:
    return ds1_train() + ds1_cal()


def ds2(include_202: bool = False) -> list[int]:
    s = config.splits()["ds2"]
    return list(s["test"]) + (list(s["sensitivity_extra"]) if include_202 else [])


def _check_access(record: int, allow_test: bool) -> None:
    if record in ds2(include_202=True) and not allow_test:
        raise TestSetAccessError(
            f"Record {record} is in DS2. Pass allow_test=True only for the frozen DS2 run."
        )


@dataclass(frozen=True)
class Record:
    name: int
    signal: np.ndarray       # MLII, millivolts, float64
    fs: int
    ann_sample: np.ndarray   # reference beat sample indices
    ann_symbol: np.ndarray   # MIT-BIH symbols
    ann_aami: np.ndarray     # AAMI class per beat ("N", "S", "V", "F", "Q")


def load_record(record: int, *, allow_test: bool = False, db_dir: Path = MITDB_DIR) -> Record:
    """Load the MLII lead (chosen by name) and the reference beat annotations."""
    _check_access(record, allow_test)
    path = str(db_dir / str(record))
    lead = config.pipeline()["lead"]
    rec = wfdb.rdrecord(path)
    if lead not in rec.sig_name:
        raise ValueError(f"Record {record} has no {lead} lead: {rec.sig_name}")
    sig = rec.p_signal[:, rec.sig_name.index(lead)]

    ann = wfdb.rdann(path, "atr")
    symbols = np.asarray(ann.symbol)
    classes = np.array([aami_class(s) for s in symbols], dtype=object)
    is_beat = classes != None  # noqa: E711 (elementwise on object array)
    return Record(
        name=record,
        signal=sig,
        fs=int(rec.fs),
        ann_sample=np.asarray(ann.sample)[is_beat],
        ann_symbol=symbols[is_beat],
        ann_aami=classes[is_beat].astype(str),
    )
