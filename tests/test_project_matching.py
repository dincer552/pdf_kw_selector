from project_discovery import discover_project_from_text
from project_matching import match_discoveries, match_project_names, match_discovery_lists


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
    assert result.right_name == "Florya Uçus Egitim Binasi G"


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
