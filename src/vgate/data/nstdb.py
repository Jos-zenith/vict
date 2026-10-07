"""MIT-BIH Noise Stress Test Database noise records (em, ma, bw)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import wfdb

from vgate import config

NSTDB_DIR = config.DATA_DIR / "nstdb"


def load_noise(kind: str, channel: int = 0, db_dir: Path = NSTDB_DIR) -> np.ndarray:
    """Full noise recording ``kind`` in {"em", "ma", "bw"} at 360 Hz."""
    if kind not in config.splits()["noise"]["types"]:
        raise ValueError(f"Unknown noise type {kind!r}")
    rec = wfdb.rdrecord(str(db_dir / kind))
    return rec.p_signal[:, channel]


def block(noise: np.ndarray, index: int, fs: int = 360) -> np.ndarray:
    """2-minute block ``index`` (1-based). Blocks 1-7 lie in the development half."""
    n = config.splits()["noise"]["block_s"] * fs
    start = (index - 1) * n
    if start + n > len(noise):
        raise IndexError(f"Block {index} runs past the end of the recording")
    return noise[start : start + n]


def is_dev_block(noise: np.ndarray, index: int, fs: int = 360) -> bool:
    """True if the block lies entirely in the first (development) half."""
    n = config.splits()["noise"]["block_s"] * fs
    return index * n <= len(noise) // 2
