from pathlib import Path

from project_discovery import discover_project, discover_project_from_text, normalize_project_name


def test_explicit_project_name_field_wins_over_project_header():
    pages = [
        "Project Florya Uçus Egitim Binasi G\nUnit Reference AHU-A-1",
        "Proje Name:\nFlorya Uçuş Eğitim Binası Faz – 1-AHU\nOrder Number:\n25341501",
    ]
    result = discover_project_from_text(pages)

    assert result.project_name == "Florya Uçuş Eğitim Binası Faz – 1-AHU"
    assert result.project_source == "project_name_field"
    assert result.project_page == 2
    assert result.confidence == "HIGH"
    assert any(c.source == "project_header" for c in result.candidates)


def test_normalization_handles_turkish_case_and_dash():
    assert normalize_project_name("Florya Uçuş Eğitim Binası Faz – 1-AHU") == "florya ucus egitim binasi faz 1 ahu"
    assert normalize_project_name("Florya Uçus Egitim Binasi G") == "florya ucus egitim binasi g"


def test_real_ahu_selection_pdf():
    result = discover_project(Path("/mnt/data/AHU_A_1.pdf"))
    assert result.project_name == "Florya Uçuş Eğitim Binası Faz – 1-AHU"
    assert result.project_source == "project_name_field"
    assert result.project_page == 1
