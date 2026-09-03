from motor_database import MotorRecord
from motor_compare import compare_motor_records
from stage2_pdf_discovery import _extract_connection_page, _summary_quantities, _apply_summary_quantities, build_pdf2_motor_records


def test_supply_motor_connection_extracts_7_5_kw():
    text = "AHU_EF_01 Supply Motor Connections-1 400 / 3Ph / 50Hz 7,5 kW 3~ M -U1 7,5 kW / 3x 380-480 VAC"
    result = _extract_connection_page(text, 8, "AHU-EF-01")
    assert result is not None
    assert result.component_type == "Vantilatör"
    assert result.component_role == "supply_fan"
    assert result.value_kw == 7.5
    assert result.source_page == 8


def test_return_motor_connection_extracts_5_5_kw():
    text = "AHU_EF_01 Return Motor Connections-1 400 / 3Ph / 50Hz 5,5 kW 3~ M -U2 5,5 kW / 3x 380-480 VAC"
    result = _extract_connection_page(text, 9, "AHU-EF-01")
    assert result is not None
    assert result.component_type == "Aspiratör"
    assert result.component_role == "return_fan"
    assert result.value_kw == 5.5


def test_activation_motor_connection_is_not_return_or_exhaust_fan():
    text = "AHU_EF_01 Activation Motor Connections-1 400 / 3Ph / 50Hz 1,18 kW 3~ M"
    result = _extract_connection_page(text, 8, "AHU-EF-01")
    assert result is None


def test_summary_preserves_2x1_quantities():
    pages = ["Unit Reference AHU-03 Fan Motor Power / Nominal Rpm 22 [kW] (2x1) / 1473 15 [kW] (2x1) / 1466"]
    assert _summary_quantities(pages) == {"supply_fan": (22.0, "2x1"), "return_fan": (15.0, "2x1")}


def test_two_return_connection_pages_remain_two_physical_motors():
    results = [
        _extract_connection_page("VE.A.D.10 Return Motor Connections-1 4 kW 3~ -U1 4 kW / 3x 380-480 VAC", 9, "VE.A.D.10"),
        _extract_connection_page("VE.A.D.10 Return Motor Connections-2 4 kW 3~ -U2 4 kW / 3x 380-480 VAC", 10, "VE.A.D.10"),
    ]
    results = [r for r in results if r is not None]
    results = _apply_summary_quantities(results, {"return_fan": (4.0, "2x1")})
    assert len(results) == 2
    assert [r.source_page for r in results] == [9, 10]
    assert [r.quantity for r in results] == ["1x1", "1x1"]
    records = []
    for i, result in enumerate(results, 1):
        records.extend(build_pdf2_motor_records(result, start_index=i))
    assert [r.component_label for r in records] == ["Asp 1", "Asp 2"]
    assert [r.source_page for r in records] == [9, 10]
    assert all(r.power_kw == 4.0 for r in records)


def test_pdf2_group_expands_to_physical_motors():
    from stage2_pdf_discovery import PDF2MotorResult
    result = PDF2MotorResult("AHU-03", "Vantilatör", "supply_fan", 22.0, "2x1", 7, "Rated Power [kW] 22,000 x (2x1)")
    records = build_pdf2_motor_records(result)
    assert [r.component_label for r in records] == ["Vant 1", "Vant 2"]
    assert all(r.power_kw == 22.0 for r in records)


def test_physical_motor_comparison_matches_same_motor():
    a = MotorRecord("AHU-EF-01", "AHU", "Vantilatör", 1, "Vant 1", 7.5, "1x1", 1, 6)
    b = MotorRecord("AHU_EF_01", "AHU", "Vantilatör", 1, "Vant 1", 7.5, "1x1", 1, 8)
    result = compare_motor_records([a], [b])
    assert len(result) == 1
    assert result[0].status == "MATCH"
    assert result[0].difference_kw == 0.0


def test_physical_motor_comparison_detects_mismatch():
    a = MotorRecord("AHU-EF-01", "AHU", "Aspiratör", 1, "Asp 1", 5.5, "1x1", 1, 6)
    b = MotorRecord("AHU-EF-01", "AHU", "Aspiratör", 1, "Asp 1", 4.0, "1x1", 1, 9)
    result = compare_motor_records([a], [b])
    assert result[0].status == "MISMATCH"
    assert result[0].difference_kw == 1.5
