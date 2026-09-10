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
    try:
        digest = hashlib.sha256()
        total = 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                total += len(chunk)
        result = digest.hexdigest()
        debug("SHA-256 hesaplandı", path=str(path), bytes=total, sha256=result)
        return result
    except Exception as exc:
        calculation_error("sha256", exc, path=str(path))
        raise


def _select_asset(assets: list[dict]) -> dict:
    """Prefer immutable commit-named assets; fall back to legacy latest asset."""
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
    available_assets = [a.get("name") for a in assets]
    raise RuntimeError(f"GitHub release içinde güncelleme EXE'si bulunamadı. Mevcut assetler={available_assets}")


def check_for_update(current_exe: Path | None = None) -> dict:
    """Return latest-release metadata and whether it differs from the running EXE."""
    try:
        release = _request_json(RELEASE_API)
        assets = release.get("assets") or []
        asset = _select_asset(assets)
        remote_digest = (asset.get("digest") or "").replace("sha256:", "").lower()
        current = Path(current_exe or sys.executable).resolve()
        current_exists = current.exists()
        current_digest = _sha256(current).lower() if current_exists else ""
        same = bool(remote_digest) and bool(current_digest) and current_digest == remote_digest
        download_url = asset.get("url") or asset.get("browser_download_url")
        if not download_url:
            raise RuntimeError("Güncelleme EXE indirme adresi GitHub'dan alınamadı.")
        info("Güncelleme kontrolü tamamlandı", release=release.get("tag_name"), release_name=release.get("name"), published_at=release.get("published_at"), asset=asset.get("name"), asset_id=asset.get("id"), asset_size=asset.get("size"), asset_content_type=asset.get("content_type"), current_exe=str(current), current_exists=current_exists, current_sha256=current_digest, remote_sha256=remote_digest, available=not same, download_endpoint=download_url, browser_download_url=asset.get("browser_download_url"))
        return {"version": release.get("name") or release.get("tag_name") or "latest", "published_at": release.get("published_at"), "download_url": download_url, "browser_download_url": asset.get("browser_download_url"), "asset_api_url": asset.get("url"), "asset_id": asset.get("id"), "asset_name": asset.get("name"), "asset_size": asset.get("size"), "digest": remote_digest, "current_digest": current_digest, "available": not same}
    except Exception as exc:
        exception("Güncelleme kontrolü başarısız", exc)
        raise


def _cache_busted(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query.append(("_cache", str(time.time_ns())))
        result = urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))
        debug("Güncelleme URL cache-bypass hazırlandı", original_url=url, request_url=result)
        return result
    except Exception as exc:
        calculation_error("güncelleme URL cache-bypass", exc, url=url)
        raise


def _download_request(url: str, *, start: int | None = None):
    headers = {
        "User-Agent": "PDF-KW-Selector-Updater",
        "Accept": "application/octet-stream",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if start is not None and start > 0:
        headers["Range"] = f"bytes={start}-"
    return urllib.request.Request(url, headers=headers)


def download_update(download_url: str, *, expected_digest: str | None = None, asset_id: int | None = None, browser_download_url: str | None = None, expected_size: int | None = None) -> Path:
    """Download, inspect and verify the replacement EXE, retrying truncated GitHub CDN responses with ranges."""
    fd, raw_path = tempfile.mkstemp(prefix="pdf_kw_selector_update_", suffix=".exe")
    os.close(fd)
    target = Path(raw_path)
    expected = (expected_digest or "").replace("sha256:", "").lower()
    total_expected = int(expected_size) if expected_size is not None else None
    info("EXE indirme başladı", url=download_url, endpoint_type="asset_api" if "/releases/assets/" in download_url else "browser_or_other", asset_id=asset_id, expected_sha256=expected or None, expected_size=total_expected, browser_download_url=browser_download_url, target=str(target))
    try:
        target.unlink(missing_ok=True)
        offset = 0
        max_attempts = 12
        for attempt in range(1, max_attempts + 1):
            request_url = _cache_busted(download_url) if offset == 0 else download_url
            request = _download_request(request_url, start=offset if offset else None)
            mode = "wb" if offset == 0 else "ab"
            with urllib.request.urlopen(request, timeout=180) as response:
                content_type = response.headers.get("Content-Type")
                content_length = response.headers.get("Content-Length")
                content_range = response.headers.get("Content-Range")
                final_url = response.geturl()
                status = getattr(response, "status", None)
                info("EXE HTTP cevabı alındı", attempt=attempt, status=status, final_url=final_url, content_type=content_type, content_length=content_length, content_range=content_range, resume_offset=offset)
                if offset > 0 and status not in (200, 206):
                    raise RuntimeError(f"GitHub devam indirmesi beklenmeyen HTTP durumu verdi: {status}")
                with target.open(mode) as output:
                    received = 0
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        received += len(chunk)
                        offset += len(chunk)
                        if offset % (5 * 1024 * 1024) < len(chunk):
                            debug("EXE indirme ilerlemesi", bytes=offset, target=str(target), attempt=attempt)

            actual_size = target.stat().st_size
            if total_expected is None:
                if content_length and content_length.isdigit():
                    total_expected = (offset if status == 206 else int(content_length))
                elif status == 206 and content_range:
                    match = re.search(r"/([0-9]+)$", content_range)
                    if match:
                        total_expected = int(match.group(1))

            complete = total_expected is None or actual_size >= total_expected
            if complete:
                break

            warning("GitHub CDN yanıtı eksik geldi; devam indirilecek", attempt=attempt, received_this_request=received, downloaded_bytes=actual_size, expected_bytes=total_expected, asset_id=asset_id)
            offset = actual_size
            time.sleep(min(attempt, 3))
        else:
            raise RuntimeError(f"GitHub EXE indirmesi tamamlanamadı: {offset}/{total_expected or '?'} byte")

        total = target.stat().st_size
        if total == 0:
            raise RuntimeError("GitHub boş dosya döndürdü.")
        if total_expected is not None and total != total_expected:
            raise RuntimeError(f"GitHub Content-Length ile indirilen byte sayısı uyuşmuyor: beklenen={total_expected}, gerçek={total}")
        with target.open("rb") as handle:
            signature = handle.read(2)
        debug("İndirilen dosya imzası kontrol edildi", signature=signature.hex(), is_pe=signature == b"MZ", bytes=total)
        if signature != b"MZ":
            raise RuntimeError("GitHub'dan indirilen dosya Windows EXE (MZ) değil.")
        digest = _sha256(target).lower()
        info("EXE indirme tamamlandı", bytes=total, sha256=digest, expected_sha256=expected or None, target=str(target))
        if expected and digest != expected:
            error("EXE SHA-256 doğrulaması başarısız", expected_sha256=expected, actual_sha256=digest, bytes=total, request_url=download_url, asset_id=asset_id, browser_download_url=browser_download_url, target=str(target))
            raise RuntimeError("İndirilen EXE'nin SHA-256 doğrulaması başarısız. " f"Beklenen={expected}, Gerçek={digest}")
        if expected:
            info("EXE SHA-256 doğrulaması başarılı", sha256=digest, asset_id=asset_id)
        return target
    except urllib.error.HTTPError as exc:
        target.unlink(missing_ok=True)
        body = exc.read(1000).decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        error("EXE indirme HTTP hatası", url=download_url, status=exc.code, reason=exc.reason, body=body, asset_id=asset_id)
        raise RuntimeError(f"EXE indirilemedi: HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        target.unlink(missing_ok=True)
        error("EXE indirme ağ hatası", url=download_url, reason=str(exc.reason), asset_id=asset_id)
        raise RuntimeError(f"EXE indirilemedi: {exc.reason}") from exc
    except Exception as exc:
        target.unlink(missing_ok=True)
        exception("EXE indirme/doğrulama hatası", exc, url=download_url, target=str(target), asset_id=asset_id)
        raise


def apply_update(temp_exe: str, target_exe: str, parent_pid: int) -> None:
    temp_path = Path(temp_exe)
    target_path = Path(target_exe)
    info("Güncelleme uygulama yardımcısı başladı", temp=str(temp_path), target=str(target_path), parent_pid=parent_pid)
    for attempt in range(120):
        running = _pid_running(parent_pid)
        debug("Eski EXE kapanma kontrolü", attempt=attempt + 1, parent_pid=parent_pid, running=running)
        if not running:
            break
        time.sleep(0.25)
    else:
        error("Güncelleme için eski program kapanmadı", parent_pid=parent_pid)
        raise RuntimeError("Eski program kapatılamadı.")
    try:
        if not temp_path.exists():
            raise FileNotFoundError(f"Güncelleme geçici EXE'si bulunamadı: {temp_path}")
        if temp_path.stat().st_size <= 0:
            raise RuntimeError("Güncelleme geçici EXE'si boş.")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp_path, target_path)
        info("Yeni EXE hedefe taşındı", target=str(target_path), size=target_path.stat().st_size)
        subprocess.Popen([str(target_path)], close_fds=True)
        info("Yeni EXE yeniden başlatıldı", target=str(target_path))
    except Exception as exc:
        exception("Güncelleme EXE değiştirme/yeniden başlatma hatası", exc, temp=str(temp_path), target=str(target_path))
        raise


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        warning("Geçersiz PID ile process kontrolü istendi", pid=pid)
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=5)
            running = str(pid) in result.stdout
            debug("Windows process durumu okundu", pid=pid, running=running, returncode=result.returncode)
            return running
        except Exception as exc:
            exception("Process durumu kontrol edilemedi", exc, pid=pid)
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def restart_with_update(temp_exe: Path, target_exe: Path | None = None) -> None:
    target = Path(target_exe or sys.executable).resolve()
    info("Güncelleme yeniden başlatma hazırlanıyor", temp=str(temp_exe), target=str(target), parent_pid=os.getpid())
    try:
        if not temp_exe.exists():
            raise FileNotFoundError(f"Güncelleme EXE'si bulunamadı: {temp_exe}")
        subprocess.Popen([str(target), "--apply-update", str(temp_exe), str(target), str(os.getpid())], close_fds=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        info("Güncelleme yardımcısı process'i başlatıldı", target=str(target))
    except Exception as exc:
        exception("Güncelleme yardımcısı başlatılamadı", exc, target=str(target), temp=str(temp_exe))
        raise
    raise SystemExit(0)
