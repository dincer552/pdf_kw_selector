from project_discovery import discover_project_from_text, normalize_project_name


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


def test_multiline_project_name_skips_following_document_labels():
    result = discover_project_from_text([
        "Proje Name:",
        "Order Number:",
        "25341501",
        "Unit Number:",
        "AHU-A-1",
        "Florya Uçuş Eğitim Binası Faz – 1-AHU",
    ])
    assert result.project_name == "Florya Uçuş Eğitim Binası Faz – 1-AHU"


def test_generic_fan_air_volume_is_not_a_project_name():
    result = discover_project_from_text(["Project Name: Supply Fan Air Volume"])
    assert result.project_name is None
    assert result.project_name_normalized is None


def test_normalization_handles_turkish_case_and_dash():
    assert normalize_project_name("Florya Uçuş Eğitim Binası Faz – 1-AHU") == "florya ucus egitim binasi faz 1 ahu"
    assert normalize_project_name("Florya Uçus Egitim Binasi G") == "florya ucus egitim binasi g"


def test_project_name_can_be_inline():
    result = discover_project_from_text(["Project Name: Florya Uçuş Eğitim Binası"])
    assert result.project_name == "Florya Uçuş Eğitim Binası"
    assert result.project_source == "project_name_field"
