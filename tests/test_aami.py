from vgate.data.aami import aami_class, is_v


def test_mapping():
    assert [aami_class(s) for s in "NLRej"] == ["N"] * 5
    assert [aami_class(s) for s in "AaJS"] == ["S"] * 4
    assert is_v("V") and is_v("E") and not is_v("F")
    assert aami_class("/") == "Q"
    assert aami_class("+") is None  # rhythm annotation, not a beat
