"""PDF viewer launcher with page navigation support."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

from app_logger import debug, exception, info, warning


def _find_windows_executable(names: list[str], search_subdirs: list[str]) -> str | None:
    """Find an executable in PATH or standard Program Files locations on Windows."""
    for name in names:
        found = shutil.which(name)
        if found and Path(found).is_file():
            return found

    candidates_dirs = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", ""),
    ]
    for base in candidates_dirs:
        if not base:
            continue
        base_path = Path(base)
        for subdir in search_subdirs:
            p = base_path / subdir
            if p.is_file():
                return str(p)
    return None


def _find_acrobat() -> str | None:
    return _find_windows_executable(
        ["AcroRd32.exe", "Acrobat.exe", "AcroRd32", "Acrobat"],
        [
            r"Adobe\Acrobat DC\Acrobat\Acrobat.exe",
            r"Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
            r"Adobe\Acrobat\Acrobat.exe",
            r"Adobe\Reader\AcroRd32.exe",
            r"Adobe\Acrobat Reader 2020\Reader\AcroRd32.exe",
            r"Adobe\Acrobat 2020\Acrobat\Acrobat.exe",
        ],
    )


def _find_edge() -> str | None:
    return _find_windows_executable(
        ["msedge.exe", "msedge"],
        [
            r"Microsoft\Edge\Application\msedge.exe",
        ],
    )


def _find_chrome() -> str | None:
    return _find_windows_executable(
        ["chrome.exe", "chrome"],
        [
            r"Google\Chrome\Application\chrome.exe",
        ],
    )


def _find_sumatra() -> str | None:
    return _find_windows_executable(
        ["SumatraPDF.exe", "SumatraPDF"],
        [
            r"SumatraPDF\SumatraPDF.exe",
        ],
    )


def _find_foxit() -> str | None:
    return _find_windows_executable(
        ["FoxitPDFReader.exe", "FoxitReader.exe", "FoxitPDFReader", "FoxitReader"],
        [
            r"Foxit Software\Foxit PDF Reader\FoxitPDFReader.exe",
            r"Foxit Software\Foxit Reader\FoxitReader.exe",
        ],
    )


def _detect_windows_default_pdf_progid() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg  # type: ignore[import-not-found]
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.pdf\UserChoice",
        ) as key:
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")
            if prog_id:
                return str(prog_id)
    except Exception:
        pass
    try:
        import winreg  # type: ignore[import-not-found]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r".pdf") as key:
            prog_id, _ = winreg.QueryValueEx(key, "")
            if prog_id:
                return str(prog_id)
    except Exception:
        pass
    return None


def open_pdf_at_page(pdf_path: str | Path, page: int | None = None) -> bool:
    """Open a PDF file at a specific page number (1-based index)."""
    try:
        p = Path(pdf_path).resolve()
        if not p.is_file():
            warning("Açılmak istenen PDF dosyası bulunamadı", path=str(pdf_path))
            return False

        try:
            page_num = max(1, int(page)) if page is not None else 1
        except (ValueError, TypeError):
            page_num = 1

        path_str = str(p)
        file_uri = p.as_uri() + f"#page={page_num}"

        info("PDF açma isteği", path=path_str, page=page_num, platform=sys.platform)

        if sys.platform == "win32":
            # 1. Check user choice from registry
            prog_id = (_detect_windows_default_pdf_progid() or "").casefold()

            # If user's default viewer is Acrobat/Reader
            if "acro" in prog_id:
                acrobat = _find_acrobat()
                if acrobat:
                    debug("Acrobat ile açılıyor (UserChoice)", acrobat=acrobat)
                    subprocess.Popen([acrobat, "/A", f"page={page_num}", path_str])
                    return True

            # If user's default viewer is SumatraPDF
            if "sumatra" in prog_id:
                sumatra = _find_sumatra()
                if sumatra:
                    debug("SumatraPDF ile açılıyor (UserChoice)", sumatra=sumatra)
                    subprocess.Popen([sumatra, "-page", str(page_num), path_str])
                    return True

            # If user's default viewer is Foxit
            if "foxit" in prog_id:
                foxit = _find_foxit()
                if foxit:
                    debug("Foxit ile açılıyor (UserChoice)", foxit=foxit)
                    subprocess.Popen([foxit, "/A", f"page={page_num}", path_str])
                    return True

            # If user's default is Edge
            if "edge" in prog_id:
                edge = _find_edge()
                if edge:
                    debug("Edge ile açılıyor (UserChoice)", edge=edge, uri=file_uri)
                    subprocess.Popen([edge, file_uri])
                    return True

            # If user's default is Chrome
            if "chrome" in prog_id:
                chrome = _find_chrome()
                if chrome:
                    debug("Chrome ile açılıyor (UserChoice)", chrome=chrome, uri=file_uri)
                    subprocess.Popen([chrome, file_uri])
                    return True

            # If default viewer not launched yet, check installed applications in priority order:
            # 1) Adobe Acrobat/Reader
            acrobat = _find_acrobat()
            if acrobat:
                debug("Acrobat bulundu, açılıyor", acrobat=acrobat)
                subprocess.Popen([acrobat, "/A", f"page={page_num}", path_str])
                return True

            # 2) Edge (natively installed on Windows 10/11)
            edge = _find_edge()
            if edge:
                debug("Edge bulundu, açılıyor", edge=edge, uri=file_uri)
                subprocess.Popen([edge, file_uri])
                return True

            # 3) Chrome
            chrome = _find_chrome()
            if chrome:
                debug("Chrome bulundu, açılıyor", chrome=chrome, uri=file_uri)
                subprocess.Popen([chrome, file_uri])
                return True

            # 4) SumatraPDF
            sumatra = _find_sumatra()
            if sumatra:
                debug("SumatraPDF bulundu, açılıyor", sumatra=sumatra)
                subprocess.Popen([sumatra, "-page", str(page_num), path_str])
                return True

            # 5) Try opening URL via webbrowser
            try:
                webbrowser.open(file_uri)
                return True
            except Exception:
                pass

            # 6) Fallback to os.startfile
            try:
                os.startfile(path_str)
                return True
            except Exception as e:
                exception("os.startfile başarısız", e, path=path_str)

        elif sys.platform == "darwin":  # macOS
            try:
                subprocess.Popen(["open", file_uri])
                return True
            except Exception:
                subprocess.Popen(["open", path_str])
                return True

        else:  # Linux
            for viewer_cmd in [
                ["evince", "-p", str(page_num), path_str],
                ["okular", "-p", str(page_num), path_str],
                ["xpdf", path_str, str(page_num)],
            ]:
                if shutil.which(viewer_cmd[0]):
                    subprocess.Popen(viewer_cmd)
                    return True

            try:
                subprocess.Popen(["xdg-open", file_uri])
                return True
            except Exception:
                try:
                    subprocess.Popen(["xdg-open", path_str])
                    return True
                except Exception:
                    webbrowser.open(file_uri)
                    return True

        return False
    except Exception as exc:
        exception("PDF açılırken beklenmedik hata oluştu", exc, path=str(pdf_path), page=page)
        return False
