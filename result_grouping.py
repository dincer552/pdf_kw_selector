from __future__ import annotations

from collections.abc import Iterable, Sequence

from ahu_matching import normalize_equipment_id


SPACER_ROW = ("", "", "", "", "", "", "", "", "", "")


def _key(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def group_result_rows(rows: Iterable[Sequence[object]]) -> list[tuple[object, ...]]:
    """Sort motor rows by project/AHU and hide repeated group labels.

    A blank spacer is inserted between different project/AHU groups. The first
    row of each group keeps Project and AHU; following motor rows leave those
    two cells blank so the table reads as a visual hierarchy.
    """
    normalized: list[tuple[object, ...]] = [tuple(row) for row in rows]
    normalized.sort(
        key=lambda row: (
            _key(row[0] if len(row) > 0 else ""),
            _key(normalize_equipment_id(row[1]) if len(row) > 1 else ""),
            _key(row[2] if len(row) > 2 else ""),
            _key(row[3] if len(row) > 3 else ""),
        )
    )

    output: list[tuple[object, ...]] = []
    previous_group: tuple[str, str] | None = None
    for row in normalized:
        project = row[0] if len(row) > 0 else ""
        ahu = normalize_equipment_id(row[1]) if len(row) > 1 else ""
        group = (_key(project), _key(ahu))

        if previous_group is not None and group != previous_group:
            output.append(SPACER_ROW)

        mutable = list(row)
        if previous_group == group:
            if len(mutable) > 0:
                mutable[0] = ""
            if len(mutable) > 1:
                mutable[1] = ""
        else:
            if len(mutable) > 1:
                mutable[1] = normalize_equipment_id(mutable[1]) or mutable[1]

        output.append(tuple(mutable))
        previous_group = group

    return output
