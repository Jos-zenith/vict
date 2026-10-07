import numpy as np

from vgate.evaluation.operating import defer_cutoff, highest_threshold, retention
from vgate.windows import WindowTable


def _table(n_true, lost):
    """Minimal table: thresholds 0, 1, 2 (default 0); lost_v rows given per window."""
    n = len(n_true)
    z = np.zeros(n)
    lost = np.asarray(lost)
    return WindowTable(
        record=np.ones(n, int), split=np.full(n, "cal"), copy=np.full(n, "noisy"),
        noise_type=np.full(n, "em"), offset=np.zeros(n, int), snr_db=z, t0=np.arange(n),
        n_beats=np.full(n, 10), svm_margin_min=z, svm_margin_mean=z, svm_margin_p10=z,
        log_qsqi=z, log_psqi=z, log_ksqi=z, log_bassqi=z, n_true_v=np.asarray(n_true),
        n_pred_v=np.zeros_like(lost), false_v=np.zeros_like(lost), lost_v=lost,
        risky=np.zeros(n, bool), thresholds=np.array([0.0, 1.0, 2.0]),
    )  # fmt: skip


def test_highest_threshold_keeps_retention():
    t = _table([2, 2], [[0, 1, 2], [0, 0, 1]])  # retention 1.0, 0.75, 0.25
    assert highest_threshold(t, 0.75) == 1 and highest_threshold(t, 0.8) == 0
    assert retention(t, 1) == 0.75


def test_defer_cutoff_respects_retention_cap_and_groups():
    t = _table([1] * 10, [[0, 0, 0]] * 10)
    risk = np.linspace(1, 0, 10)  # window 0 riskiest
    assert defer_cutoff(t, risk, 0.0, 0, cap=0.8) == risk[1]  # cap: defer 2 of 10
    assert defer_cutoff(t, risk, 0.85, 0, cap=0.5) == risk[0]  # retention: defer 1
    groups = np.array(["a"] * 3 + ["b"] * 7)  # the 3 riskiest are all group a
    assert defer_cutoff(t, risk, 0.0, 0, cap=0.7, groups=groups) == np.inf  # a: 0.3 * 3 < 1
    assert defer_cutoff(t, risk, 0.0, 0, cap=0.6, groups=groups) == risk[0]  # a: 1.2 -> 1
