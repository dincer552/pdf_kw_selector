from pathlib import Path

from pdf_master_scan import build_physical_motor_records, scan_pdf


ROOT = Path(__file__).resolve().parents[1]
PDF1 = ROOT / "HKS-12.pdf"
PDF2 = ROOT / "HKS_12.pdf"


def test_master_scan_pdf1_reads_project_equipment_motors_and_ebm_once_path():
    scan = scan_pdf(PDF1, "PDF1")

    assert scan.side == "PDF1"
    assert scan.page_count > 0
    assert scan.project.project_name
    assert "HKS-12" in scan.equipment.unique_ids()
    assert {result.value_kw for result in scan.pdf1_motors} >= {4.0, 7.5}
    assert isinstance(scan.pdf1_ebm_pages, tuple)
    assert scan.pdf2_motors == ()


def test_master_scan_pdf2_does_not_run_pdf1_ebm_collection():
    scan = scan_pdf(PDF2, "PDF2")

    assert scan.side == "PDF2"
    assert scan.page_count > 0
    assert "HKS-12" in scan.equipment.unique_ids()
    assert {result.value_kw for result in scan.pdf2_motors} >= {4.0, 7.5}
    assert scan.pdf1_motors == ()
    assert scan.pdf1_ebm_pages == ()


def test_master_scan_builds_physical_motor_records_from_cached_results():
    pdf1 = scan_pdf(PDF1, "PDF1")
    pdf2 = scan_pdf(PDF2, "PDF2")

    pdf1_records = build_physical_motor_records(pdf1)
    pdf2_records = build_physical_motor_records(pdf2)

    assert len(pdf1_records) == 2
    assert len(pdf2_records) == 2
    assert sorted(record.power_kw for record in pdf1_records) == [4.0, 7.5]
    assert sorted(record.power_kw for record in pdf2_records) == [4.0, 7.5]
