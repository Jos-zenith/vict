"""Load the committed TOML configs (configs/*.toml)."""

from __future__ import annotations

import tomllib
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs"
DATA_DIR = ROOT / "data" / "raw"
RESULTS_DIR = ROOT / "results"


@cache
def load(name: str) -> dict:
    """Return configs/<name>.toml as a dict, e.g. load("pipeline")."""
    with open(CONFIG_DIR / f"{name}.toml", "rb") as f:
        return tomllib.load(f)


def pipeline() -> dict:
    return load("pipeline")


def splits() -> dict:
    return load("splits")
