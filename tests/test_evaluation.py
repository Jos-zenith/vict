import numpy as np

from vgate.evaluation.matching import match
from vgate.evaluation.stats import bootstrap_ci


def test_match_one_to_one_within_tolerance():
    ref = np.array([100, 500, 900])
    det = np.array([105, 110, 700, 905])
    d2r, r2d = match(det, ref, tol=54)
    assert d2r.tolist() == [0, -1, -1, 2]
    assert r2d.tolist() == [0, -1, 3]


def test_bootstrap_point_estimate():
    ref = np.array([10, 20, 30, 40])
    arm = ref * 0.5
    est, lo, hi = bootstrap_ci(ref, arm, n=500)
    assert np.isclose(est, 0.5) and np.isclose(lo, 0.5) and np.isclose(hi, 0.5)
