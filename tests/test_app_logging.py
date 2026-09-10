from __future__ import annotations

import app_logger


def test_log_file_can_record_exception(tmp_path, monkeypatch):
    monkeypatch.setattr(app_logger, "log_directory", lambda: tmp_path)
    monkeypatch.setattr(app_logger, "_LOGGER", None)

    try:
        raise ValueError("test calculation failure")
    except ValueError as exc:
        app_logger.exception("Test hesaplama hatası", exc, operation="unit-test")

    text = (tmp_path / "pdf_kw_selector.log").read_text(encoding="utf-8")
    assert "Test hesaplama hatası" in text
    assert "ValueError" in text
    assert "test calculation failure" in text
    assert "unit-test" in text
