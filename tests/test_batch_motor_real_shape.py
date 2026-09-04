from motor_database import MotorRecord
from motor_compare import compare_motor_records
from stage2_pdf_discovery import PDF2MotorResult, build_pdf2_motor_records


def test_two_supply_motors_compare_as_two_physical_records():
    pdf1 = [
        MotorRecord("AHU-A-1", "AHU", "Vantilatör", 1, "Vant 1", 11.0, "2x1", 2, 1),
        MotorRecord("AHU-A-1", "AHU", "Vantilatör", 2, "Vant 2", 11.0, "2x1", 2, 1),
    ]
    pdf2 = build_pdf2_motor_records(
        PDF2MotorResult(
            "AHU-A-1", "Vantilatör", "supply_fan", 11.0, "2x1", 1,
            "summary-only fallback: Fan Motor Power / Nominal Rpm", "medium"
        )
    )
    result = compare_motor_records(pdf1, pdf2)
    assert len(result) == 2
    assert [item.component_label for item in result] == ["Vant 1", "Vant 2"]
    assert all(item.status == "MATCH" for item in result)
    assert all(item.difference_kw == 0.0 for item in result)
