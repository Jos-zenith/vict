import pytest

from vgate.data import mitdb


def test_split_sizes():
    assert len(mitdb.ds1_train()) == 16
    assert len(mitdb.ds1_cal()) == 6
    assert len(mitdb.ds2()) == 21


def test_splits_disjoint_and_exclusions():
    from vgate import config

    train, cal, test = set(mitdb.ds1_train()), set(mitdb.ds1_cal()), set(mitdb.ds2())
    assert not (train & cal) and not (train & test) and not (cal & test)
    paced = set(config.splits()["excluded"]["paced"])
    assert not (paced & (train | cal | test | {202}))
    assert 202 not in test and 201 in train


def test_ds2_access_is_guarded():
    with pytest.raises(mitdb.TestSetAccessError):
        mitdb.load_record(100)
    with pytest.raises(mitdb.TestSetAccessError):
        mitdb.load_record(202)


def test_pipeline_refuses_ds2_copies_without_the_flag():
    from vgate.pipeline import Copy, process

    with pytest.raises(mitdb.TestSetAccessError):
        process(Copy(100, "test", "none"))
