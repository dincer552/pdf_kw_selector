from ahu_matching import match_ahu_ids, normalize_equipment_id, score_ahu_ids


def test_florya_c_series_distinct_ahus():
    assert normalize_equipment_id("AHU_C_1") == "AHU-C-1"
    assert normalize_equipment_id("AHU_C_1_A") == "AHU-C-1-A"
    assert normalize_equipment_id("AHU_C_2_A") == "AHU-C-2-A"

    assert score_ahu_ids("AHU_C_1", "AHU_C_1_A")[1] not in {"EXACT", "NORMALIZED_MATCH"}
    assert score_ahu_ids("AHU_C_1", "AHU_C_2_A")[1] == "NO_MATCH"
    assert score_ahu_ids("AHU_C_1_A", "AHU_C_2_A")[1] == "NO_MATCH"


def test_florya_c_series_expected_same_id_match():
    for ahu in ("AHU_C_1", "AHU_C_1_A", "AHU_C_2_A"):
        result = match_ahu_ids(ahu, ahu, left_page=1, right_page=1)
        assert result.status == "EXACT"
        assert result.score == 1.0
