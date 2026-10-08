from project_discovery import discover_project_from_text
from project_matching import match_discoveries, match_project_names, match_discovery_lists
from batch_analysis import _one_to_one_files_for_ahu


class _Document:
    def __init__(self, path, equipment):
        self.path = path
        self.equipment = equipment


def test_duplicate_pdf_candidates_are_reduced_to_one_pair():
    left = [_Document("selection.pdf", ("AHU-01",))]
    right = [
        _Document("01-C.pdf", ("AHU-01",)),
        _Document("01-C_REV.pdf", ("AHU-01",)),
    ]

    left_files, right_files = _one_to_one_files_for_ahu(left, right, "AHU-01")

    assert left_files == ("selection.pdf",)
    assert right_files == ("01-C.pdf",)


def test_user_selected_duplicate_pdf_is_used():
    left = [_Document("selection.pdf", ("AHU-01",))]
    right = [
        _Document("01-C.pdf", ("AHU-01",)),
        _Document("01-C_REV.pdf", ("AHU-01",)),
    ]

    left_files, right_files = _one_to_one_files_for_ahu(
        left, right, "AHU-01", "01-C_REV.pdf"
    )

    assert left_files == ("selection.pdf",)
    assert right_files == ("01-C_REV.pdf",)


def test_exact_project_match():
    result = match_project_names("Florya Uçuş Eğitim Binası", "Florya Ucus Egitim Binasi")
    assert result.status == "EXACT"
    assert result.score == 1.0


def test_real_florya_variants_match_with_high_confidence():
    left = discover_project_from_text([
        "Proje Name:\nFlorya Uçuş Eğitim Binası Faz – 1-AHU\nOrder Number:\n25341501"
    ])
    right = discover_project_from_text([
        "Project Florya Uçus Egitim Binasi G\nUnit Reference AHU-A-1"
    ])
    result = match_discoveries(left, right)
    assert result.status == "HIGH_CONFIDENCE"
    assert result.score >= 0.85
    assert result.left_name == "Florya Uçuş Eğitim Binası Faz – 1-AHU"
    assert result.right_name == "Project Florya Uçus Egitim Binasi G"


def test_systemair_project_header_drops_creation_metadata():
    result = discover_project_from_text([
        "Project Florya Uçus Egitim Binasi G Creation date 23.03.2026",
        "Project Florya Uçus Egitim Binasi Revision Date 27.03.2026",
    ])
    assert result.project_name == "Project Florya Uçus Egitim Binasi G"
    assert result.project_name_normalized == "project florya ucus egitim binasi g"


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
    assert result.project_source == "project_name_field"


def test_project_header_keeps_raw_prefix_for_simple_header():
    result = discover_project_from_text(["Project Alpha Building"])
    assert result.project_name == "Project Alpha Building"


def test_numeric_conflict_requires_review():
    result = match_project_names("Florya Eğitim Binası 1", "Florya Eğitim Binası 2")
    assert result.status == "REVIEW_REQUIRED"


def test_unrelated_projects_do_not_match():
    result = match_project_names("Florya Uçuş Eğitim Binası", "Ankara Hastane Kampusu")
    assert result.status == "NO_MATCH"
    assert result.score < 0.75


def test_discovery_lists_are_one_to_one():
    left = [
        discover_project_from_text(["Project Alpha Building"]),
        discover_project_from_text(["Project Beta Building"]),
    ]
    right = [
        discover_project_from_text(["Project Beta Building"]),
        discover_project_from_text(["Project Alpha Building"]),
    ]
    matches = match_discovery_lists(left, right)
    assert len(matches) == 2
    assert {m.left_name for m in matches} == {"Project Alpha Building", "Project Beta Building"}
    assert all(m.status == "EXACT" for m in matches)
