"""GitHub Releases based self-updater for the Windows desktop app."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from app_logger import calculation_error, debug, error, exception, info, warning

REPO = "dincer552/pdf_kw_selector"
RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/tags/latest"
ASSET_NAME = "PDF_KW_Selector_latest.exe"
IMMUTABLE_ASSET_RE = re.compile(r"^PDF_KW_Selector_[0-9a-f]{40}\.exe$", re.IGNORECASE)


def _request_json(url: str) -> dict:
    info("Güncelleme metadata isteği başladı", url=url)
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "PDF-KW-Selector-Updater"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read()
            debug("Güncelleme metadata HTTP cevabı alındı", status=getattr(response, "status", None), final_url=response.geturl(), content_type=response.headers.get("Content-Type"), bytes=len(raw))
            payload = json.loads(raw.decode("utf-8"))
            debug("Güncelleme metadata JSON çözüldü", keys=sorted(payload.keys()))
            return payload
    except urllib.error.HTTPError as exc:
        body = exc.read(1000).decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        error("Güncelleme metadata HTTP hatası", url=url, status=exc.code, reason=exc.reason, body=body)
        raise RuntimeError(f"GitHub güncelleme servisi HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        error("Güncelleme metadata ağ hatası", url=url, reason=str(exc.reason))
        raise RuntimeError(f"GitHub'a bağlanılamadı: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        calculation_error("güncelleme metadata JSON çözümleme", exc, url=url)
        raise RuntimeError("GitHub güncelleme cevabı geçerli JSON değil.") from exc
    except Exception as exc:
        exception("Güncelleme metadata okuma hatası", exc, url=url)
        raise


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    result = digest.hexdigest()
    debug("SHA-256 hesaplandı", path=str(path), bytes=path.stat().st_size, sha256=result)
    return result


def _select_asset(assets: list[dict]) -> dict:
    immutable = [a for a in assets if IMMUTABLE_ASSET_RE.fullmatch(str(a.get("name", ""))) and a.get("state") == "uploaded"]
    if immutable:
        immutable.sort(key=lambda a: (a.get("created_at") or "", a.get("updated_at") or ""), reverse=True)
        selected = immutable[0]
        info("Güncelleme için immutable EXE seçildi", asset=selected.get("name"), asset_id=selected.get("id"), created_at=selected.get("created_at"), size=selected.get("size"))
        return selected
    legacy = next((a for a in assets if a.get("name") == ASSET_NAME), None)
    if legacy:
        warning("Immutable updater asset bulunamadı; legacy latest asset kullanılıyor", asset_id=legacy.get("id"), size=legacy.get("size"))
        return legacy
    raise RuntimeError("GitHub release içinde güncelleme EXE'si bulunamadı.")


def check_for_update(current_exe: Path | None = None) -> dict:
    release = _request_json(RELEASE_API)
    asset = _select_asset(release.get("assets") or [])
    remote_digest = (asset.get("digest") or "").replace("sha256:", "").lower()
    current = Path(current_exe or sys.executable).resolve()
    current_digest = _sha256(current).lower() if current.exists() else ""
    same = bool(remote_digest) and current_digest == remote_digest
    download_url = asset.get("url") or asset.get("browser_download_url")
    if not download_url:
        raise RuntimeError("Güncelleme EXE indirme adresi GitHub'dan alınamadı.")
    info("Güncelleme kontrolü tamamlandı", release=release.get("tag_name"), asset=asset.get("name"), asset_id=asset.get("id"), asset_size=asset.get("size"), current_exe=str(current), current_sha256=current_digest, remote_sha256=remote_digest, available=not same, download_endpoint=download_url, browser_download_url=asset.get("browser_download_url"))
    return {"version": release.get("name") or release.get("tag_name") or "latest", "published_at": release.get("published_at"), "download_url": download_url, "browser_download_url": asset.get("browser_download_url"), "asset_api_url": asset.get("url"), "asset_id": asset.get("id"), "asset_name": asset.get("name"), "asset_size": asset.get("size"), "digest": remote_digest, "current_digest": current_digest, "available": not same}


def _cache_busted(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("_cache", str(time.time_ns())))
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))


def _open_download(url: str, start: int = 0):
    headers = {"User-Agent": "PDF-KW-Selector-Updater", "Accept": "application/octet-stream", "Cache-Control": "no-cache", "Pragma": "no-cache", "Accept-Encoding": "identity"}
    if start:
        headers["Range"] = f"bytes={start}-"
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=180)


def download_update(download_url: str, *, expected_digest: str | None = None, asset_id: int | None = None, browser_download_url: str | None = None, expected_size: int | None = None) -> Path:
    """Download an EXE; tolerate stale Content-Length, recover short CDN reads, trust SHA-256."""
    fd, raw_path = tempfile.mkstemp(prefix="pdf_kw_selector_update_", suffix=".exe")
    os.close(fd)
    target = Path(raw_path)
    expected = (expected_digest or "").replace("sha256:", "").lower()
    total_expected = int(expected_size) if expected_size is not None else None
    info("EXE indirme başladı", url=download_url, browser_download_url=browser_download_url, asset_id=asset_id, expected_sha256=expected or None, expected_size=total_expected, target=str(target))
    try:
        offset = 0
        for attempt in range(1, 16):
            # Cache-bust every request, including Range retries. Some GitHub CDN
            # paths otherwise return the same short cached response repeatedly.
            request_url = _cache_busted(download_url)
            with _open_download(request_url, offset) as response:
                status = getattr(response, "status", None)
                content_length = response.headers.get("Content-Length")
                content_range = response.headers.get("Content-Range")
                info("EXE HTTP cevabı alındı", attempt=attempt, status=status, final_url=response.geturl(), content_type=response.headers.get("Content-Type"), content_encoding=response.headers.get("Content-Encoding"), content_length=content_length, content_range=content_range, resume_offset=offset)

                if offset and status == 200:
                    warning("GitHub Range başlığını yoksaydı; dosya baştan indirilecek", attempt=attempt, resume_offset=offset)
                    target.unlink(missing_ok=True)
                    offset = 0
                    continue
                if offset and status != 206:
                    raise RuntimeError(f"GitHub devam indirmesi için beklenmeyen HTTP durumu: {status}")

                with target.open("ab" if offset else "wb") as output:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        offset += len(chunk)

                actual_size = target.stat().st_size
                if content_range:
                    match = re.search(r"/([0-9]+)$", content_range)
                    if match:
                        total_expected = int(match.group(1))
                elif total_expected is None and content_length and content_length.isdigit() and status == 200:
                    total_expected = int(content_length)
                info("EXE parça indirildi", attempt=attempt, downloaded_bytes=actual_size, expected_bytes=total_expected, status=status)

            # Size is only a recovery hint. Never reject a file merely because
            # GitHub's Content-Length is stale. SHA-256 below is authoritative.
            if expected:
                digest = _sha256(target).lower()
                if digest == expected:
                    info("EXE indirme tamamlandı ve SHA-256 doğrulandı", bytes=target.stat().st_size, sha256=digest, asset_id=asset_id)
                    return target
            if total_expected is not None and offset < total_expected:
                warning("GitHub CDN yanıtı eksik geldi; kaldığı yerden devam edilecek", attempt=attempt, downloaded_bytes=offset, expected_bytes=total_expected, missing_bytes=total_expected - offset, asset_id=asset_id)
                time.sleep(min(attempt, 3))
                continue
            # No digest match and size appears complete: retry from scratch rather
            # than ever installing an unverified executable.
            warning("EXE boyutu tamam görünmesine rağmen SHA-256 eşleşmedi; baştan denenecek", attempt=attempt, bytes=offset, expected_sha256=expected, asset_id=asset_id)
            target.unlink(missing_ok=True)
            offset = 0
            total_expected = int(expected_size) if expected_size is not None else None
            time.sleep(min(attempt, 3))

        raise RuntimeError("GitHub EXE indirildi ancak güvenilir SHA-256 doğrulaması yapılamadı.")
    except Exception as exc:
        target.unlink(missing_ok=True)
        exception("EXE indirme/doğrulama hatası", exc, url=download_url, target=str(target), asset_id=asset_id)
        raise


def apply_update(temp_exe: str, target_exe: str, parent_pid: int) -> None:
    temp_path = Path(temp_exe); target_path = Path(target_exe)
    info("Güncelleme uygulama yardımcısı başladı", temp=str(temp_path), target=str(target_path), parent_pid=parent_pid)
    for _ in range(120):
        if not _pid_running(parent_pid): break
        time.sleep(0.25)
    else: raise RuntimeError("Eski program kapatılamadı.")
    if not temp_path.exists() or temp_path.stat().st_size <= 0: raise RuntimeError("Güncelleme geçici EXE'si geçersiz.")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temp_path, target_path)
    subprocess.Popen([str(target_path)], close_fds=True)


def _pid_running(pid: int) -> bool:
    if pid <= 0: return False
    if os.name == "nt":
        try:
            result = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=5)
            return str(pid) in result.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0); return True
    except OSError:
        return False


def restart_with_update(temp_exe: Path, target_exe: Path | None = None) -> None:
    target = Path(target_exe or sys.executable).resolve()
    subprocess.Popen([str(target), "--apply-update", str(temp_exe), str(target), str(os.getpid())], close_fds=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    raise SystemExit(0)
