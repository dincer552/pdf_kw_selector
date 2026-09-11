import hashlib
import os

import app_logger
import updater


class _FakeHeaders(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class _FakeResponse:
    status = 200

    def __init__(self, payload: bytes):
        self.payload = payload
        self.offset = 0
        self.headers = _FakeHeaders({"Content-Type": "application/octet-stream", "Content-Length": str(len(payload))})

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def geturl(self):
        return "https://objects.example/final/PDF_KW_Selector_latest.exe"

    def read(self, size=-1):
        if self.offset >= len(self.payload):
            return b""
        if size < 0:
            size = len(self.payload) - self.offset
        chunk = self.payload[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk


class _TruncatedResponse(_FakeResponse):
    def __init__(self, payload: bytes, advertised_size: int):
        super().__init__(payload)
        self.headers["Content-Length"] = str(advertised_size)


def _reset_logger():
    logger = app_logger.get_logger()
    for handler in list(logger.handlers):
        try:
            handler.flush()
            handler.close()
        finally:
            logger.removeHandler(handler)
    app_logger._LOGGER = None


def _fake_mkstemp(tmp_path, filename):
    fd = os.open(os.devnull, os.O_RDWR)
    return fd, str(tmp_path / filename)


def test_calculation_error_writes_traceback(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    _reset_logger()
    try:
        try:
            raise ValueError("test calculation failure")
        except ValueError as exc:
            app_logger.calculation_error("test_operation", exc, input_value="bad")
        text = app_logger.read_log()
        assert "HESAPLAMA HATASI" in text
        assert "test_operation" in text
        assert "ValueError" in text
        assert "test calculation failure" in text
        assert "Traceback" in text
    finally:
        _reset_logger()


def test_download_update_logs_and_verifies_expected_digest(monkeypatch, tmp_path):
    payload = b"MZ" + b"test-exe-payload" * 10
    expected = hashlib.sha256(payload).hexdigest()
    captured = {}

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return _FakeResponse(payload)

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(updater.tempfile, "mkstemp", lambda prefix, suffix: _fake_mkstemp(tmp_path, "update.exe"))

    target = updater.download_update(
        "https://api.github.com/repos/dincer552/pdf_kw_selector/releases/assets/123",
        expected_digest=expected,
        asset_id=123,
    )
    try:
        assert target.exists()
        assert target.read_bytes() == payload
        assert "_cache=" in captured["url"]
        assert captured["timeout"] == 180
        assert expected == updater._sha256(target)
    finally:
        target.unlink(missing_ok=True)


def test_download_update_accepts_asset_without_sha_validation(monkeypatch, tmp_path):
    payload = b"MZ" + b"wrong-payload"

    def fake_urlopen(request, timeout=0):
        return _FakeResponse(payload)

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(updater.tempfile, "mkstemp", lambda prefix, suffix: _fake_mkstemp(tmp_path, "bad.exe"))

    target = updater.download_update(
        "https://api.github.com/repos/dincer552/pdf_kw_selector/releases/assets/123",
        expected_digest="0" * 64,
        asset_id=123,
    )
    try:
        assert target.read_bytes() == payload
    finally:
        target.unlink(missing_ok=True)


def test_download_update_retries_until_expected_size(monkeypatch, tmp_path):
    payload = b"MZ" + b"complete-exe-payload"
    calls = {"count": 0}

    def fake_urlopen(request, timeout=0):
        calls["count"] += 1
        if calls["count"] == 1:
            return _TruncatedResponse(payload[:-4], len(payload))
        response = _FakeResponse(payload[-4:])
        response.status = 206
        response.headers["Content-Range"] = f"bytes={len(payload) - 4}-{len(payload) - 1}/{len(payload)}"
        return response

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(updater.tempfile, "mkstemp", lambda prefix, suffix: _fake_mkstemp(tmp_path, "retry.exe"))

    target = updater.download_update(
        "https://github.com/example/releases/download/latest/update.exe",
        expected_size=len(payload),
        asset_id=123,
        asset_name="PDF_KW_Selector_latest.exe",
    )
    try:
        assert calls["count"] == 2
        assert target.read_bytes() == payload
    finally:
        target.unlink(missing_ok=True)
