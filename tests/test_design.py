import numpy as np
import pytest

from vgate import config, design
from vgate.features import FEATURE_NAMES

MODELS = config.RESULTS_DIR / "ds2" / "freeze-v1" / "models.npz"


def test_window_states():
    feats = np.zeros((5, len(FEATURE_NAMES)))
    det = np.array([100, 500, 900, 4000, 4400])  # 3 beats in window 0, 2 in window 1
    states = design.window_states(det, feats, np.array([0, 3600]))
    assert states[1] == "insufficient" and states[0] in ("V suspected", "no V")
    big = feats.copy()
    big[0] = 1e3 * np.sign(design.robust_weights()["coef"])  # pushes beat 0 far into V
    assert design.window_states(det, big, np.array([0]))[0] == "V suspected"


@pytest.mark.skipif(not MODELS.exists(), reason="needs the freeze-v1 DS2 run's models.npz")
def test_weights_match_the_freeze_v1_robust():
    m = np.load(MODELS)
    w = design.robust_weights()
    assert np.array_equal(np.asarray(w["coef"]), m["robust_coef"])
    assert np.array_equal(np.asarray(w["mean"]), m["robust_mean"])
    assert w["intercept"] == float(m["robust_intercept"][0])
