from types import SimpleNamespace

from status import (
    STATUS_EBM_PAPST,
    STATUS_MATCH,
    STATUS_MISMATCH,
    STATUS_ONLY_IN_PDF1,
    STATUS_ONLY_IN_PDF2,
    decide_motor_status,
    is_match_status,
)


def motor(power_kw, brand=None):
    return SimpleNamespace(power_kw=power_kw, model_brand=brand)


def test_only_literal_match_is_green():
    assert is_match_status("MATCH")
    assert is_match_status(" match ")
    assert not is_match_status("MISMATCH")
    assert not is_match_status("BA kodu eşleşti (BA550)")
    assert not is_match_status("PDF2 AHU eşleşti; motor kW karşılaştırması yapılmadı")
    assert not is_match_status("EBM_PAPST")
    assert not is_match_status("ONLY_IN_PDF1")
    assert not is_match_status("ONLY_IN_PDF2")


def test_normal_match_and_mismatch_are_decided centrally():
    match = decide_motor_status(motor(7.5), motor(7.5))
    mismatch = decide_motor_status(motor(7.5), motor(4.0))
    assert match.status == STATUS_MATCH
    assert match.difference_kw == 0.0
    assert mismatch.status == STATUS_MISMATCH
    assert mismatch.difference_kw == 3.5


def test_legacy_1_1_to_1_5_exception_is_still_match():
    result = decide_motor_status(motor(1.1), motor(1.5))
    assert result.status == STATUS_MATCH
    assert result.difference_kw == 0.4
    assert "1.1" in result.explanation and "1.5" in result.explanation


def test_special_statuses_are_decided_centrally():
    assert decide_motor_status(None, motor(7.5)).status == STATUS_ONLY_IN_PDF2
    assert decide_motor_status(motor(7.5), None).status == STATUS_ONLY_IN_PDF1
    assert decide_motor_status(motor(7.5, "EBM-Papst"), motor(7.5)).status == STATUS_EBM_PAPST
