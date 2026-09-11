from __future__ import annotations

import updater
from updater import _cache_busted, _download_request_url, _select_asset


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


def test_download_request_url_keeps_direct_release_url_unchanged():
    original = "https://github.com/dincer552/pdf_kw_selector/releases/download/latest/update.zip"
    assert _download_request_url(original) == original


def test_select_asset_prefers_canonical_latest_exe_over_stale_immutable_assets():
    assets = [
        {"name": "PDF_KW_Selector_latest.exe", "id": 100, "state": "uploaded", "digest": "sha256:old", "size": 10},
        {"name": "PDF_KW_Selector_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.exe", "id": 101, "state": "uploaded", "digest": "sha256:a", "created_at": "2026-09-10T05:00:00Z", "size": 20},
        {"name": "PDF_KW_Selector_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.exe", "id": 102, "state": "uploaded", "digest": "sha256:b", "created_at": "2026-09-10T06:00:00Z", "size": 30},
        {"name": "PDF_KW_Selector_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.zip", "id": 103, "state": "uploaded", "digest": "sha256:c", "created_at": "2026-09-10T06:00:00Z", "size": 12},
    ]
    selected = _select_asset(assets)
    assert selected["id"] == 100
    assert selected["name"] == "PDF_KW_Selector_latest.exe"


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


def test_check_for_update_prefers_direct_browser_download_url(monkeypatch, tmp_path):
    browser_url = "https://github.com/dincer552/pdf_kw_selector/releases/download/latest/update.zip"
    api_url = "https://api.github.com/repos/dincer552/pdf_kw_selector/releases/assets/123"
    monkeypatch.setattr(
        updater,
        "_request_json",
        lambda url: {
            "tag_name": "latest",
            "assets": [
                {
                    "name": "PDF_KW_Selector_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.zip",
                    "id": 123,
                    "state": "uploaded",
                    "digest": "sha256:" + "a" * 64,
                    "size": 10,
                    "url": api_url,
                    "browser_download_url": browser_url,
                }
            ],
        },
    )
    current = tmp_path / "current.exe"
    current.write_bytes(b"current")

    result = updater.check_for_update(current)

    assert result["download_url"] == browser_url
    assert result["asset_api_url"] == api_url
