from pathlib import Path

import batch_analysis
import pdf_master_scan
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
    assert {(r.component_type, r.component_index) for r in pdf1_records} == {("Vantilatör", 1), ("Aspiratör", 1)}
    assert {(r.component_type, r.component_index) for r in pdf2_records} == {("Vantilatör", 1), ("Aspiratör", 1)}


def test_master_scan_cache_reads_a_pdf_once(monkeypatch):
    calls = []
    original = pdf_master_scan._read_pages_once

    def counted(path):
        calls.append(str(path))
        return original(path)

    monkeypatch.setattr(pdf_master_scan, "_read_pages_once", counted)
    pdf_master_scan.clear_master_scan_cache()
    first = pdf_master_scan.scan_pdf(PDF1, "PDF1")
    second = pdf_master_scan.scan_pdf(PDF1, "PDF1")
    assert first is second
    assert calls == [str(PDF1.resolve())]


def test_batch_discovery_uses_master_scan(monkeypatch):
    calls = []
    original = batch_analysis.scan_pdf

    def counted(path, side):
        calls.append((str(path), side))
        return original(path, side)

    monkeypatch.setattr(batch_analysis, "scan_pdf", counted)
    pdf_master_scan.clear_master_scan_cache()
    documents = batch_analysis._discover_documents([PDF1, PDF2], "PDF1")
    assert len(documents) == 2
    assert calls == [(str(PDF1.resolve()), "PDF1"), (str(PDF2.resolve()), "PDF1")]
