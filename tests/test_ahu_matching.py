from ahu_matching import (
    discover_equipment_from_text,
    match_ahu_ids,
    match_ahu_lists,
    normalize_equipment_id,
    score_ahu_ids,
)


def test_normalize_common_ahu_forms():
    assert normalize_equipment_id("AHU_A_1") == "AHU-A-1"
    assert normalize_equipment_id("AHU-A-01") == "AHU-A-1"
    assert normalize_equipment_id("AHU_A_1A") == "AHU-A-1A"
    assert normalize_equipment_id("AHU_A_2") == "AHU-A-2"


def test_prefixed_ahu_forms_normalize_to_same_equipment():
    assert normalize_equipment_id("AD_AHU_01") == "AHU-1"
    assert normalize_equipment_id("AD-AHU-01") == "AHU-1"
    result = discover_equipment_from_text(["Unit Number AD_AHU_01\nAD_AHU_01"])
    assert "AHU-1" in result.unique_ids()


def test_discover_distinct_ahus_from_pages():
    pages = [
        "AHU_A_1\nUnit Reference AHU-A-1",
        "AHU_A_1A\nUnit Reference AHU-A-1A",
        "AHU_A_2\nUnit Reference AHU-A-2",
    ]
    result = discover_equipment_from_text(pages)
    assert set(result.unique_ids()) == {"AHU-A-1", "AHU-A-1A", "AHU-A-2"}


def test_exact_and_normalized_match():
    assert score_ahu_ids("AHU_A_1", "AHU-A-01")[1] in {"EXACT", "NORMALIZED_MATCH"}
    result = match_ahu_ids("AHU_A_1", "AHU-A-01", left_page=1, right_page=1)
    assert result.status in {"EXACT", "NORMALIZED_MATCH"}
    assert result.score >= 0.98


def test_distinct_ahu_suffix_is_not_auto_matched():
    result = match_ahu_ids("AHU-A-1", "AHU-A-1A")
    assert result.status != "EXACT"
    assert result.status != "NORMALIZED_MATCH"


def test_ahu_lists_expose_unmatched_equipment():
    left = discover_equipment_from_text(["Unit Reference AHU-A-1", "Unit Reference AHU-A-1A"])
    right = discover_equipment_from_text(["Unit Reference AHU-A-2"])
    matches = match_ahu_lists(list(left.equipment_ids), list(right.equipment_ids))
    statuses = {m.status for m in matches}
    assert "ONLY_IN_PDF1" in statuses
    assert "ONLY_IN_PDF2" in statuses


def test_hks_unit_is_discovered_and_matches_underscore_variant():
    left = discover_equipment_from_text(["Unit Number HKS-12"])
    right = discover_equipment_from_text(["Unit Number HKS_12"])
    assert left.unique_ids() == ("HKS-12",)
    assert right.unique_ids() == ("HKS-12",)
    result = match_ahu_ids("HKS-12", "HKS_12")
    assert result.status == "EXACT"
    assert result.score == 1.0


def test_ks_unit_is_discovered_and_matches_underscore_variant():
    left = discover_equipment_from_text(["KS-00.02"])
    right = discover_equipment_from_text(["KS_00.02"])
    assert left.unique_ids() == ("KS-00.02",)
    assert right.unique_ids() == ("KS-00.02",)
    result = match_ahu_ids("KS-00.02", "KS_00.02")
    assert result.status == "EXACT"
    assert result.score == 1.0


def test_ks_unit_reference_is_supported():
    result = discover_equipment_from_text(["Unit Number KS_01.03"])
    assert result.unique_ids() == ("KS-01.03",)


def test_unit_reference_value_has_priority_over_ahukit_text():
    result = discover_equipment_from_text([
        "Project Ekol Sada Hastanesi Unit Reference HKS-12",
        "AHUKit Count 3 Pcs AHUKit",
    ])
    assert result.unique_ids() == ("HKS-12",)


def test_ahukit_is_not_an_equipment_id():
    result = discover_equipment_from_text(["AHUKit Count: 3 Pcs", "AHUKit"])
    assert result.unique_ids() == ()
