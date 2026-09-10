from result_grouping import SPACER_ROW, group_result_rows


def test_groups_same_project_and_ahu_and_keeps_motor_rows_together():
    rows = [
        ("Project B", "AHU-B-2", "Vant 2", "Vantilatör", "11", "11", "0", "MATCH", "2", "8"),
        ("Project A", "AHU-A-1", "Vant 2", "Vantilatör", "11", "11", "0", "MATCH", "1", "7"),
        ("Project A", "AHU-A-1", "Vant 1", "Vantilatör", "11", "11", "0", "MATCH", "1", "6"),
        ("Project A", "AHU-A-2", "Asp 1", "Aspiratör", "4", "5", "1", "MISMATCH", "3", "9"),
    ]

    result = group_result_rows(rows)

    assert result[0][0:2] == ("Project A", "AHU-A-1")
    assert result[1][0:2] == ("", "")
    assert result[2] == SPACER_ROW
    assert result[3][0:2] == ("Project A", "AHU-A-2")
    assert result[4] == SPACER_ROW
    assert result[5][0:2] == ("Project B", "AHU-B-2")


def test_normalizes_ahu_label_inside_a_group():
    rows = [
        ("Project", "AHU_A_1", "Vant 1", "Vantilatör", "11", "11", "0", "MATCH", "1", "2"),
        ("Project", "AHU-A-01", "Vant 2", "Vantilatör", "11", "11", "0", "MATCH", "1", "3"),
    ]

    result = group_result_rows(rows)

    assert result[0][1] == "AHU-A-1"
    assert result[1][0:2] == ("", "")
    assert SPACER_ROW not in result
