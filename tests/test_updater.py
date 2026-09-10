from __future__ import annotations

from updater import _cache_busted


def test_cache_busted_url_changes_query_without_losing_original_url():
    original = "https://github.com/dincer552/pdf_kw_selector/releases/download/latest/PDF_KW_Selector_latest.exe"
    updated = _cache_busted(original)
    assert updated.startswith(original + "?_cache=")
    assert updated != original


def test_cache_busted_preserves_existing_query():
    original = "https://example.test/file.exe?download=1"
    updated = _cache_busted(original)
    assert "download=1" in updated
    assert "&_cache=" in updated
