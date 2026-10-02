"""Match detections to reference beats within +/-150 ms (scoring only)."""

from __future__ import annotations

import numpy as np


def match(det: np.ndarray, ref: np.ndarray, tol: int) -> tuple[np.ndarray, np.ndarray]:
    """One-to-one matching, closest pairs first.

    Returns (det_to_ref, ref_to_det): index of the partner, or -1 if unmatched.
    """
    det_to_ref = np.full(len(det), -1, dtype=int)
    ref_to_det = np.full(len(ref), -1, dtype=int)
    if len(det) == 0 or len(ref) == 0:
        return det_to_ref, ref_to_det
    cand = []
    for i, k in enumerate(np.searchsorted(ref, det)):
        for r in (k - 1, k):
            if 0 <= r < len(ref) and abs(int(det[i]) - int(ref[r])) <= tol:
                cand.append((abs(int(det[i]) - int(ref[r])), i, r))
    for _, i, r in sorted(cand):
        if det_to_ref[i] < 0 and ref_to_det[r] < 0:
            det_to_ref[i], ref_to_det[r] = r, i
    return det_to_ref, ref_to_det
