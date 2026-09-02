from local_database import connect, list_motors, replace_project_motors
from motor_database import expand_motor_group


def test_database_stores_each_physical_motor_separately(tmp_path):
    db = connect(tmp_path / "test.db")
    records = []
    records += expand_motor_group(
        equipment_id="AHU1",
        equipment_type="AHU",
        component_type="vantilatör",
        group="2x1",
        power_kw=3.0,
        source_page=6,
    )
    records += expand_motor_group(
        equipment_id="AHU1",
        equipment_type="AHU",
        component_type="aspiratör",
        group="3x1",
        power_kw=2.2,
        source_page=7,
    )

    replace_project_motors(db, records)
    rows = list_motors(db)

    assert [r["component_label"] for r in rows] == [
        "Vant 1", "Vant 2", "Asp 1", "Asp 2", "Asp 3"
    ]
    assert [r["power_kw"] for r in rows] == [3.0, 3.0, 2.2, 2.2, 2.2]
    assert [r["source_page"] for r in rows] == [6, 6, 7, 7, 7]
