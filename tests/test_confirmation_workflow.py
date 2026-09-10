from confirmation_workflow import _flexible_ahu_key


def test_flexible_ahu_key_ignores_separators_and_leading_zeroes():
    assert _flexible_ahu_key("AD-AHU-01") == _flexible_ahu_key("AD_AHU_1")
    assert _flexible_ahu_key("AHU-A-001") == _flexible_ahu_key("AHU_A_1")


def test_flexible_ahu_key_keeps_distinct_suffixes_distinct():
    assert _flexible_ahu_key("AHU-A-1") != _flexible_ahu_key("AHU-A-1A")
