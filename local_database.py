"""SQLite storage for extracted motor records."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from motor_database import MotorRecord, build_comparison_key


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
    connection = sqlite3.connect(str(db_path))
    connection.execute(SCHEMA)
    connection.commit()
    return connection


def replace_project_motors(connection: sqlite3.Connection, records: list[MotorRecord]) -> None:
    """Replace the normalized motor list with the latest PDF extraction."""
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


def list_motors(connection: sqlite3.Connection) -> list[dict]:
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
    return [dict(row) for row in rows]


def comparison_key_from_row(row: dict) -> tuple[str, str, int]:
    return (
        str(row["equipment_id"]).upper(),
        str(row["component_type"]).strip().lower(),
        int(row["component_index"]),
    )
