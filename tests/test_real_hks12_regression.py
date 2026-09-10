from pathlib import Path

from ahu_matching import discover_equipment, match_ahu_ids
from motor_compare import compare_motor_records
from stage1_page_discovery import build_stage1_motor_records, find_rated_motor_powers_in_pdf
from stage2_pdf_discovery import build_pdf2_motor_records, find_pdf2_motor_powers


ROOT = Path(__file__).resolve().parents[1]
PDF1 = ROOT / "HKS-12.pdf"
PDF2 = ROOT / "HKS_12.pdf"


def test_real_hks12_pdfs_discover_same_equipment():
    left = discover_equipment(PDF1)
    right = discover_equipment(PDF2)

    assert left.unique_ids() == ("HKS-12",)
    assert right.unique_ids() == ("HKS-12",)

    match = match_ahu_ids(left.unique_ids()[0], right.unique_ids()[0])
    assert match.status == "EXACT"
    assert match.score == 1.0


def test_real_hks12_pdfs_extract_and_compare_two_motors():
    pdf1_results = find_rated_motor_powers_in_pdf(PDF1)
    pdf2_results = find_pdf2_motor_powers(PDF2)

    assert {(x.component_role, x.value_kw, x.quantity) for x in pdf1_results} == {
        ("supply_fan", 7.5, "1x1"),
        ("return_fan", 4.0, "1x1"),
    }
    assert {(x.component_role, x.value_kw, x.quantity) for x in pdf2_results} == {
        ("supply_fan", 7.5, "1x1"),
        ("return_fan", 4.0, "1x1"),
    }
    assert all(x.equipment_id == "HKS-12" for x in pdf1_results)
    assert all(x.equipment_id == "HKS-12" for x in pdf2_results)

    pdf1_motors = [record for result in pdf1_results for record in build_stage1_motor_records(result)]
    pdf2_motors = [record for result in pdf2_results for record in build_pdf2_motor_records(result)]

    comparisons = compare_motor_records(pdf1_motors, pdf2_motors)

    assert len(comparisons) == 2
    assert all(item.status == "MATCH" for item in comparisons)
    assert {(item.component_type, item.pdf1_kw, item.pdf2_kw, item.difference_kw) for item in comparisons} == {
        ("Vantilatör", 7.5, 7.5, 0.0),
        ("Aspiratör", 4.0, 4.0, 0.0),
    }
