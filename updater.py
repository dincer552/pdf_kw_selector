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
import urllib.request

REPO = "dincer552/pdf_kw_selector"
RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/tags/latest"
ASSET_NAME = "PDF_KW_Selector_latest.exe"


def _request_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "PDF-KW-Selector-Updater"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_for_update(current_exe: Path | None = None) -> dict:
    """Return latest-release metadata and whether it differs from the running EXE."""
    release = _request_json(RELEASE_API)
    assets = release.get("assets") or []
    asset = next((item for item in assets if item.get("name") == ASSET_NAME), None)
    if not asset:
        raise RuntimeError("GitHub'da güncel EXE bulunamadı.")

    remote_digest = (asset.get("digest") or "").replace("sha256:", "").lower()
    current = Path(current_exe or sys.executable)
    same = bool(remote_digest) and current.exists() and _sha256(current).lower() == remote_digest
    return {
        "version": release.get("name") or release.get("tag_name") or "latest",
        "published_at": release.get("published_at"),
        "download_url": asset.get("browser_download_url"),
        "digest": remote_digest,
        "available": not same,
    }


def download_update(download_url: str) -> Path:
    """Download the replacement EXE into a temporary file and return its path."""
    fd, raw_path = tempfile.mkstemp(prefix="pdf_kw_selector_update_", suffix=".exe")
    os.close(fd)
    target = Path(raw_path)
    request = urllib.request.Request(
        download_url,
        headers={"User-Agent": "PDF-KW-Selector-Updater", "Accept": "application/octet-stream"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response, target.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
        return target
    except Exception:
        target.unlink(missing_ok=True)
        raise


def apply_update(temp_exe: str, target_exe: str, parent_pid: int) -> None:
    """Run in a helper process, wait for the old app, replace it, and relaunch."""
    temp_path = Path(temp_exe)
    target_path = Path(target_exe)
    for _ in range(120):
        if not _pid_running(parent_pid):
            break
        time.sleep(0.25)
    else:
        raise RuntimeError("Eski program kapatılamadı.")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temp_path, target_path)
    subprocess.Popen([str(target_path)], close_fds=True)


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def restart_with_update(temp_exe: Path, target_exe: Path | None = None) -> None:
    """Start this EXE in updater mode and exit the current application."""
    target = Path(target_exe or sys.executable).resolve()
    subprocess.Popen(
        [str(target), "--apply-update", str(temp_exe), str(target), str(os.getpid())],
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    raise SystemExit(0)
