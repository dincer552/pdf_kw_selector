from pathlib import Path

from ahu_matching import discover_equipment_from_text
from batch_analysis import BatchDocument, _group_documents
from project_discovery import discover_project_from_text
from stage2_pdf_discovery import _summary_quantities


def test_batch_documents_group_by_project():
    p1 = discover_project_from_text(["Proje Name: Florya Uçuş Eğitim Binası Faz – 1-AHU"])
    p2 = discover_project_from_text(["Project Florya Uçus Egitim Binasi G"])
    d1 = BatchDocument("a.pdf", "PDF1", p1, ("AHU-A-1",))
    d2 = BatchDocument("b.pdf", "PDF1", p1, ("AHU-A-1A",))
    d3 = BatchDocument("c.pdf", "PDF2", p2, ("AHU-A-1",))

    grouped = _group_documents([d1, d2, d3])

    assert len(grouped) == 2
    assert len(grouped[p1.project_name_normalized]) == 2
    assert len(grouped[p2.project_name_normalized]) == 1


def test_pdf2_single_supply_summary_is_supported():
    text = "AHU-A-1 Fan Motor Power / Nominal Rpm 11 [kW] (2x1) / 1466 [1/min]"
    summary = _summary_quantities([text])
    assert summary["supply_fan"] == (11.0, "2x1")


def test_equipment_discovery_keeps_distinct_ahus():
    result = discover_equipment_from_text([
        "Unit Reference AHU-A-1",
        "Unit Reference AHU-A-1A",
        "Unit Reference AHU-A-2",
    ])
    assert set(result.unique_ids()) == {"AHU-A-1", "AHU-A-1A", "AHU-A-2"}
