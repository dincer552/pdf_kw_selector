from __future__ import annotations

from updater import _cache_busted, _select_asset


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


def test_select_asset_prefers_newest_immutable_zip_over_exe_assets():
    assets = [
        {"name": "PDF_KW_Selector_latest.exe", "id": 100, "state": "uploaded", "digest": "sha256:old", "size": 10},
        {"name": "PDF_KW_Selector_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.exe", "id": 101, "state": "uploaded", "digest": "sha256:a", "created_at": "2026-09-10T05:00:00Z", "size": 20},
        {"name": "PDF_KW_Selector_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.exe", "id": 102, "state": "uploaded", "digest": "sha256:b", "created_at": "2026-09-10T06:00:00Z", "size": 30},
        {"name": "PDF_KW_Selector_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.zip", "id": 103, "state": "uploaded", "digest": "sha256:c", "created_at": "2026-09-10T06:00:00Z", "size": 12},
    ]
    selected = _select_asset(assets)
    assert selected["id"] == 103
    assert selected["name"].endswith("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.zip")


def test_select_asset_prefers_newest_immutable_exe_when_no_zip_exists():
    assets = [
        {"name": "PDF_KW_Selector_latest.exe", "id": 100, "state": "uploaded", "digest": "sha256:old", "size": 10},
        {"name": "PDF_KW_Selector_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.exe", "id": 101, "state": "uploaded", "digest": "sha256:a", "created_at": "2026-09-10T05:00:00Z", "size": 20},
        {"name": "PDF_KW_Selector_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.exe", "id": 102, "state": "uploaded", "digest": "sha256:b", "created_at": "2026-09-10T06:00:00Z", "size": 30},
    ]
    assert _select_asset(assets)["id"] == 102


def test_select_asset_falls_back_to_legacy_latest():
    assets = [
        {"name": "PDF_KW_Selector_latest.exe", "id": 100, "state": "uploaded", "digest": "sha256:old"},
    ]
    assert _select_asset(assets)["id"] == 100
