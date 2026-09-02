from pdf_kw_selector import normalize_equipment_id, select_fan_motor_power


def test_equipment_id_normalization():
    assert normalize_equipment_id("AHU-1") == "AHU1"
    assert normalize_equipment_id("AHU_01") == "AHU1"
    assert normalize_equipment_id("AHU 001") == "AHU1"


def test_fan_motor_power_beats_unit_total_power():
    text = """
    AHU-1
    Fan Motor: 3 kW
    Unit Total Power: 4 kW
    Total Heating: 20 kW
    """
    result = select_fan_motor_power(text)
    assert result is not None
    assert result.value_kw == 3
    assert result.rejected is False


def test_watts_are_converted_to_kw():
    result = select_fan_motor_power("Supply Fan Motor Power 750 W")
    assert result is not None
    assert result.value_kw == 0.75


def test_aggregate_only_returns_none():
    result = select_fan_motor_power("Unit Total Power: 4 kW")
    assert result is None
