"""Checks against the downloaded databases. Skipped until data/raw is populated."""

import pytest

from vgate import config
from vgate.data import mitdb

pytestmark = pytest.mark.data
needs_mitdb = pytest.mark.skipif(
    not (mitdb.MITDB_DIR / "100.hea").exists(), reason="run scripts/download_data.py first"
)


@needs_mitdb
def test_record_114_uses_mlii_by_name():
    rec = mitdb.load_record(114)
    assert rec.fs == 360 and rec.signal.ndim == 1


@needs_mitdb
def test_ds1_v_counts():
    exp = config.splits()["expected_v_beats"]
    for name, recs in [("ds1_train", mitdb.ds1_train()), ("ds1_cal", mitdb.ds1_cal())]:
        n = sum(int((mitdb.load_record(r).ann_aami == "V").sum()) for r in recs)
        assert n == exp[name], name
