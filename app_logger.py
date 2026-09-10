"""Central application logging for PDF kW Selector.

All application modules use this logger so failures are persisted outside the
EXE directory and can be inspected from the GUI. The logger records the
operation, exception type/message, traceback and structured context whenever
possible.
"""
from __future__ import annotations

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import threading
import traceback
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
            try:
                base += "\n" + self.formatException(record.exc_info)
            except Exception:
                base += "\n[traceback could not be formatted]"
        return base


_LOGGER: logging.Logger | None = None


def _build_handler() -> RotatingFileHandler:
    directory = log_directory()
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_file(), maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(ContextFormatter())
    return handler


def get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    logger = logging.getLogger("pdf_kw_selector")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if not logger.handlers:
        logger.addHandler(_build_handler())

    _LOGGER = logger
    return logger


def _log(level: int, message: str, **context: Any) -> None:
    try:
        get_logger().log(level, message, extra={"context": context})
    except Exception:
        # Logging itself must never crash the application.
        try:
            print(f"LOGGER FAILURE | {message} | {_safe_context(context)}", file=sys.stderr)
        except Exception:
            pass


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
    try:
        get_logger().error(message, exc_info=exc_info, extra={"context": payload})
    except Exception:
        try:
            print(f"LOGGER FAILURE | {message} | {_safe_context(payload)}", file=sys.stderr)
            if exc_info:
                traceback.print_exception(*exc_info)
        except Exception:
            pass


def calculation_error(operation: str, exc: BaseException, **context: Any) -> None:
    """Record a parsing/calculation failure explicitly as an ERROR event."""
    exception("HESAPLAMA HATASI", exc, operation=operation, **context)


def read_log(max_chars: int = 300_000) -> str:
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
    """Clear the active log and reopen the handler so Windows file locking cannot corrupt future entries."""
    logger = get_logger()
    path = log_file()
    try:
        for handler in list(logger.handlers):
            try:
                handler.flush()
                handler.close()
            finally:
                logger.removeHandler(handler)
        path.unlink(missing_ok=True)
        logger.addHandler(_build_handler())
    except Exception as exc:
        try:
            if not logger.handlers:
                logger.addHandler(_build_handler())
        except Exception:
            pass
        exception("Log temizlenemedi", exc, path=str(path))
        raise


def install_exception_hook() -> None:
    """Persist otherwise-unhandled GUI, main-thread and worker-thread errors."""
    def handle_exception(exc_type, exc_value, exc_traceback):
        if exc_type is KeyboardInterrupt:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        try:
            get_logger().critical(
                "YAKALANMAMIŞ UYGULAMA HATASI",
                exc_info=(exc_type, exc_value, exc_traceback),
                extra={"context": {"exception_type": exc_type.__name__, "exception": str(exc_value)}},
            )
        finally:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)

    def handle_thread_exception(args):
        try:
            get_logger().critical(
                "YAKALANMAMIŞ THREAD HATASI",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
                extra={
                    "context": {
                        "thread": getattr(args.thread, "name", "unknown"),
                        "exception_type": args.exc_type.__name__,
                        "exception": str(args.exc_value),
                    }
                },
            )
        except Exception:
            pass

    sys.excepthook = handle_exception
    if hasattr(threading, "excepthook"):
        threading.excepthook = handle_thread_exception


def startup(version: str = "v0.5.3") -> None:
    get_logger()
    install_exception_hook()
    info(
        "Uygulama başlatıldı",
        pid=os.getpid(),
        executable=sys.executable,
        version=version,
        cwd=os.getcwd(),
        platform=os.name,
        log_file=str(log_file()),
    )
