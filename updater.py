"""GitHub Releases based self-updater for the Windows desktop app."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from app_logger import debug, error, exception, info, warning

REPO = "dincer552/pdf_kw_selector"
RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/tags/latest"
ASSET_NAME = "PDF_KW_Selector_latest.exe"


def _request_json(url: str) -> dict:
    info("Güncelleme metadata isteği başladı", url=url)
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "PDF-KW-Selector-Updater"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
            debug("Güncelleme metadata alındı", status=response.status, url=url)
            return payload
    except urllib.error.HTTPError as exc:
        error("Güncelleme metadata HTTP hatası", url=url, status=exc.code, reason=exc.reason)
        raise RuntimeError(f"GitHub güncelleme servisi HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        error("Güncelleme metadata ağ hatası", url=url, reason=str(exc.reason))
        raise RuntimeError(f"GitHub'a bağlanılamadı: {exc.reason}") from exc
    except Exception as exc:
        exception("Güncelleme metadata okuma hatası", exc, url=url)
        raise


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_for_update(current_exe: Path | None = None) -> dict:
    """Return latest-release metadata and whether it differs from the running EXE."""
    try:
        release = _request_json(RELEASE_API)
        assets = release.get("assets") or []
        asset = next((item for item in assets if item.get("name") == ASSET_NAME), None)
        if not asset:
            raise RuntimeError(f"GitHub release içinde {ASSET_NAME} bulunamadı.")

        remote_digest = (asset.get("digest") or "").replace("sha256:", "").lower()
        current = Path(current_exe or sys.executable)
        current_digest = _sha256(current).lower() if current.exists() else ""
        same = bool(remote_digest) and bool(current_digest) and current_digest == remote_digest
        download_url = asset.get("url") or asset.get("browser_download_url")
        if not download_url:
            raise RuntimeError("Güncelleme EXE indirme adresi GitHub'dan alınamadı.")
        info(
            "Güncelleme kontrolü tamamlandı",
            release=release.get("tag_name"),
            asset=ASSET_NAME,
            current_sha256=current_digest,
            remote_sha256=remote_digest,
            available=not same,
            download_endpoint=download_url,
        )
        return {
            "version": release.get("name") or release.get("tag_name") or "latest",
            "published_at": release.get("published_at"),
            "download_url": download_url,
            "browser_download_url": asset.get("browser_download_url"),
            "asset_api_url": asset.get("url"),
            "asset_id": asset.get("id"),
            "digest": remote_digest,
            "current_digest": current_digest,
            "available": not same,
        }
    except Exception as exc:
        exception("Güncelleme kontrolü başarısız", exc)
        raise


def _cache_busted(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("_cache", str(time.time_ns())))
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))


def download_update(download_url: str) -> Path:
    """Download the replacement EXE into a temporary file and return its path.

    The Releases asset API endpoint is preferred because repeatedly replacing an
    asset with the same filename can otherwise return a stale CDN object.
    A cache-busting query parameter is also added as a second layer of defense.
    """
    fd, raw_path = tempfile.mkstemp(prefix="pdf_kw_selector_update_", suffix=".exe")
    os.close(fd)
    target = Path(raw_path)
    request_url = _cache_busted(download_url)
    info("EXE indirme başladı", url=request_url, target=str(target))
    request = urllib.request.Request(
        request_url,
        headers={
            "User-Agent": "PDF-KW-Selector-Updater",
            "Accept": "application/octet-stream",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as output:
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                total += len(chunk)
        if total < 1024 * 1024:
            warning("İndirilen EXE beklenenden küçük", bytes=total, target=str(target))
        digest = _sha256(target)
        info("EXE indirme tamamlandı", bytes=total, sha256=digest, target=str(target))
        return target
    except urllib.error.HTTPError as exc:
        target.unlink(missing_ok=True)
        error("EXE indirme HTTP hatası", url=request_url, status=exc.code, reason=exc.reason)
        raise RuntimeError(f"EXE indirilemedi: HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        target.unlink(missing_ok=True)
        error("EXE indirme ağ hatası", url=request_url, reason=str(exc.reason))
        raise RuntimeError(f"EXE indirilemedi: {exc.reason}") from exc
    except Exception as exc:
        target.unlink(missing_ok=True)
        exception("EXE indirme hatası", exc, url=request_url, target=str(target))
        raise


def apply_update(temp_exe: str, target_exe: str, parent_pid: int) -> None:
    """Run in a helper process, wait for the old app, replace it, and relaunch."""
    temp_path = Path(temp_exe)
    target_path = Path(target_exe)
    info("Güncelleme uygulama yardımcısı başladı", temp=str(temp_path), target=str(target_path), parent_pid=parent_pid)
    for _ in range(120):
        if not _pid_running(parent_pid):
            break
        time.sleep(0.25)
    else:
        error("Güncelleme için eski program kapanmadı", parent_pid=parent_pid)
        raise RuntimeError("Eski program kapatılamadı.")

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp_path, target_path)
        info("Yeni EXE hedefe taşındı", target=str(target_path))
        subprocess.Popen([str(target_path)], close_fds=True)
        info("Yeni EXE yeniden başlatıldı", target=str(target_path))
    except Exception as exc:
        exception("Güncelleme EXE değiştirme/yeniden başlatma hatası", exc, temp=str(temp_path), target=str(target_path))
        raise


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=5,
            )
            return str(pid) in result.stdout
        except Exception as exc:
            exception("Process durumu kontrol edilemedi", exc, pid=pid)
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def restart_with_update(temp_exe: Path, target_exe: Path | None = None) -> None:
    """Start this EXE in updater mode and exit the current application."""
    target = Path(target_exe or sys.executable).resolve()
    info("Güncelleme yeniden başlatma hazırlanıyor", temp=str(temp_exe), target=str(target), parent_pid=os.getpid())
    try:
        subprocess.Popen(
            [str(target), "--apply-update", str(temp_exe), str(target), str(os.getpid())],
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        exception("Güncelleme yardımcısı başlatılamadı", exc, target=str(target))
        raise
    raise SystemExit(0)
