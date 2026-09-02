from kw_compare import compare_records, extract_power_records


def test_semantic_field_matching_and_equipment_normalization():
    pdf_a = """
    AHU-1
    Supply Fan Motor Power 3 kW (1x1)
    Unit Total Power 4 kW
    Cooling Capacity 44.63 kW
    """
    pdf_b = """
    AHU_01
    Motor Gücü: 3,000 kW
    Unit Total Power: 4 kW
    """
    a = extract_power_records(pdf_a)
    b = extract_power_records(pdf_b)
    results = compare_records(a, b)

    fan = next(r for r in results if r.field == "fan_motor_power")
    assert fan.equipment == "AHU1"
    assert fan.pdf_a_kw == 3
    assert fan.pdf_b_kw == 3
    assert fan.status == "MATCH"


def test_total_power_is_not_compared_as_fan_motor_power():
    records = extract_power_records("AHU-1\nUnit Total Power: 4 kW")
    assert all(r.field == "unit_total_power" for r in records)


def test_decimal_comma_and_watts():
    records = extract_power_records("AHU-2\nMotor Power: 750 W\n")
    assert records[0].value_kw == 0.75
