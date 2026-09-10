"""SQLite storage for extracted motor records."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app_logger import debug, exception, info
from motor_database import MotorRecord


SCHEMA = """
CREATE TABLE IF NOT EXISTS motors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id TEXT NOT NULL,
    equipment_type TEXT NOT NULL,
    component_type TEXT NOT NULL,
    component_index INTEGER NOT NULL,
    component_label TEXT NOT NULL,
    power_kw REAL,
    source_group TEXT NOT NULL,
    motor_count INTEGER NOT NULL,
    source_page INTEGER,
    confidence TEXT NOT NULL,
    UNIQUE(equipment_id, component_type, component_index)
);
"""


def connect(db_path: str | Path = "pdf_kw.db") -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(str(db_path))
        connection.execute(SCHEMA)
        connection.commit()
        info("Motor veritabanı bağlantısı açıldı", path=str(db_path))
        return connection
    except Exception as exc:
        exception("Motor veritabanı bağlantısı açılamadı", exc, path=str(db_path))
        raise


def replace_project_motors(connection: sqlite3.Connection, records: list[MotorRecord]) -> None:
    """Replace the normalized motor list with the latest PDF extraction."""
    try:
        connection.execute("DELETE FROM motors")
        connection.executemany(
            """
            INSERT INTO motors (
                equipment_id, equipment_type, component_type, component_index,
                component_label, power_kw, source_group, motor_count,
                source_page, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r.equipment_id,
                    r.equipment_type,
                    r.component_type,
                    r.component_index,
                    r.component_label,
                    r.power_kw,
                    r.source_group,
                    r.motor_count,
                    r.source_page,
                    r.confidence,
                )
                for r in records
            ],
        )
        connection.commit()
        info("Motor veritabanı güncellendi", record_count=len(records))
    except Exception as exc:
        exception("Motor veritabanı kayıt/güncelleme hatası", exc, record_count=len(records))
        raise


def list_motors(connection: sqlite3.Connection) -> list[dict]:
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT * FROM motors
            ORDER BY equipment_id,
                     CASE
                         WHEN lower(component_type) IN ('vantilatör', 'vantilator') THEN 1
                         WHEN lower(component_type) IN ('aspiratör', 'aspirator') THEN 2
                         ELSE 9
                     END,
                     component_index
            """
        ).fetchall()
        result = [dict(row) for row in rows]
        debug("Motor veritabanı okundu", record_count=len(result))
        return result
    except Exception as exc:
        exception("Motor veritabanı okuma hatası", exc)
        raise


def comparison_key_from_row(row: dict) -> tuple[str, str, int]:
    try:
        key = (
            str(row["equipment_id"]).upper(),
            str(row["component_type"]).strip().lower(),
            int(row["component_index"]),
        )
        return key
    except Exception as exc:
        exception("Motor veritabanı karşılaştırma anahtarı hesaplanamadı", exc, row=row)
        raise
