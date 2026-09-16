from status_badges import badge_colors, badge_text, is_match_status, normalize_status


def test_only_exact_match_is_a_success():
    assert is_match_status("MATCH") is True
    assert is_match_status(" match ") is True
    assert is_match_status("MISMATCH") is False
    assert is_match_status("BA kodu eşleşti (BA550)") is False
    assert is_match_status("PDF2 AHU eşleşti; motor kW karşılaştırması yapılmadı") is False
    assert is_match_status("ONLY_IN_PDF1") is False
    assert is_match_status("EBM_PAPST") is False


def test_match_is_green_and_everything_else_is_red():
    assert badge_colors("MATCH") == ("#dcfce7", "#10b981", "#064e3b")
    assert badge_colors("MISMATCH") == ("#fee2e2", "#ef4444", "#7f1d1d")
    assert badge_colors("BA kodu eşleşti (BA550)") == ("#fee2e2", "#ef4444", "#7f1d1d")


def test_badge_text_is_canonical():
    assert badge_text("MATCH") == "✓ MATCH"
    assert badge_text("MISMATCH") == "✕ MISMATCH"
    assert badge_text("BA kodu eşleşti (BA550)") == "✕ BA kodu eşleşti (BA550)"
    assert normalize_status("  PDF2   AHU eşleşti  ") == "PDF2 AHU eşleşti"
