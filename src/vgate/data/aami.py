"""AAMI class mapping of MIT-BIH beat symbols (de Chazal et al. 2004)."""

from __future__ import annotations

AAMI: dict[str, str] = {
    **dict.fromkeys(["N", "L", "R", "e", "j"], "N"),
    **dict.fromkeys(["A", "a", "J", "S"], "S"),
    **dict.fromkeys(["V", "E"], "V"),
    "F": "F",
    # Q / paced / unclassifiable: excluded from scoring
    **dict.fromkeys(["/", "f", "Q"], "Q"),
}

BEAT_SYMBOLS = frozenset(AAMI)


def aami_class(symbol: str) -> str | None:
    """AAMI class for a beat symbol, or None for non-beat annotations (rhythm, noise...)."""
    return AAMI.get(symbol)


def is_v(symbol: str) -> bool:
    return AAMI.get(symbol) == "V"
