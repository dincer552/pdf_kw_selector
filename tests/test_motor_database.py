from motor_database import build_comparison_key, expand_motor_group, parse_motor_group


def test_parse_motor_groups():
    assert parse_motor_group("1x1") == (1, 1)
    assert parse_motor_group("2x1") == (2, 1)
    assert parse_motor_group("3 × 1") == (3, 1)


def test_2x1_creates_two_vantilator_records():
    records = expand_motor_group(
        equipment_id="AHU1",
        equipment_type="AHU",
        component_type="vantilatör",
        group="2x1",
        power_kw=3.0,
        source_page=6,
    )

    assert len(records) == 2
    assert [r.component_label for r in records] == ["Vant 1", "Vant 2"]
    assert [r.component_index for r in records] == [1, 2]
    assert [r.power_kw for r in records] == [3.0, 3.0]
    assert [r.source_group for r in records] == ["2x1", "2x1"]


def test_3x1_creates_three_aspirator_records():
    records = expand_motor_group(
        equipment_id="AHU1",
        equipment_type="AHU",
        component_type="aspiratör",
        group="3x1",
        power_kw=2.2,
        source_page=6,
    )

    assert len(records) == 3
    assert [r.component_label for r in records] == ["Asp 1", "Asp 2", "Asp 3"]


def test_comparison_keys_are_unique_per_motor():
    records = expand_motor_group(
        equipment_id="AHU1",
        equipment_type="AHU",
        component_type="vantilatör",
        group="2x1",
        power_kw=3.0,
    )
    assert len({build_comparison_key(r) for r in records}) == 2
