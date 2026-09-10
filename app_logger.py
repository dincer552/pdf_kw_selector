"""Central application logging for PDF kW Selector.

Logs are written to a user-writable LOCALAPPDATA directory on Windows so the
EXE can always record failures even when it is installed outside the user's
profile. The GUI can also display the same log file.
"""
from __future__ import annotations

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from typing import Any

APP_NAME = "PDF_KW_Selector"
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 5


def log_directory() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME / "logs"
    return Path.home() / ".pdf_kw_selector" / "logs"


def log_file() -> Path:
    return log_directory() / "pdf_kw_selector.log"


def _safe_context(context: dict[str, Any]) -> str:
    if not context:
        return ""
    try:
        return " | " + json.dumps(context, ensure_ascii=False, default=str, sort_keys=True)
    except Exception:
        return " | {\"context_error\":\"unable to serialize log context\"}"


class ContextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        message = record.getMessage()
        context = getattr(record, "context", {})
        base = f"{timestamp} | {record.levelname:<8} | {record.name} | {message}{_safe_context(context)}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


_LOGGER: logging.Logger | None = None


def get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    directory = log_directory()
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("pdf_kw_selector")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if not logger.handlers:
        handler = RotatingFileHandler(
            log_file(), maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
        )
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(ContextFormatter())
        logger.addHandler(handler)

    _LOGGER = logger
    return logger


def _log(level: int, message: str, **context: Any) -> None:
    get_logger().log(level, message, extra={"context": context})


def debug(message: str, **context: Any) -> None:
    _log(logging.DEBUG, message, **context)


def info(message: str, **context: Any) -> None:
    _log(logging.INFO, message, **context)


def warning(message: str, **context: Any) -> None:
    _log(logging.WARNING, message, **context)


def error(message: str, **context: Any) -> None:
    _log(logging.ERROR, message, **context)


def exception(message: str, exc: BaseException | None = None, **context: Any) -> None:
    payload = dict(context)
    if exc is not None:
        payload.update({"exception_type": type(exc).__name__, "exception": str(exc)})
        exc_info = (type(exc), exc, exc.__traceback__)
    else:
        exc_info = sys.exc_info()
    get_logger().error(message, exc_info=exc_info, extra={"context": payload})


def read_log(max_chars: int = 200_000) -> str:
    path = log_file()
    if not path.exists():
        return "Log dosyası henüz oluşturulmadı."
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Log okunamadı: {type(exc).__name__}: {exc}"
    if len(text) > max_chars:
        return "[... eski loglar kısaltıldı ...]\n" + text[-max_chars:]
    return text


def clear_log() -> None:
    path = log_file()
    try:
        get_logger()
        for handler in get_logger().handlers:
            handler.flush()
        path.write_text("", encoding="utf-8")
    except Exception as exc:
        error("Log temizlenemedi", exception_type=type(exc).__name__, exception=str(exc))


def install_exception_hook() -> None:
    """Persist otherwise-unhandled GUI exceptions with a full traceback."""
    def handle_exception(exc_type, exc_value, exc_traceback):
        if exc_type is KeyboardInterrupt:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        try:
            get_logger().critical(
                "Yakalanmamış uygulama hatası",
                exc_info=(exc_type, exc_value, exc_traceback),
                extra={"context": {"exception_type": exc_type.__name__, "exception": str(exc_value)}},
            )
        finally:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception


def startup() -> None:
    get_logger()
    install_exception_hook()
    info("Uygulama başlatıldı", pid=os.getpid(), executable=sys.executable, version="v0.5.3")
