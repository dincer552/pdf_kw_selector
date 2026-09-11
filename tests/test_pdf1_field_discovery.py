from pdf1_field_discovery import discover_pdf1_project, discover_pdf1_unit_reference


def test_pdf1_inline_header_fields_are_parsed_exactly():
    pages = [
        "Project Ekol Sada Hastanesi Creation date 8.04.2026\n"
        "Revision Date 20.04.2026\n"
        "Unit Reference HKS-12 Revision No\n"
        "Designer Sample 3"
    ]

    project = discover_pdf1_project(pages)
    equipment = discover_pdf1_unit_reference(pages)

    assert project.project_name == "Ekol Sada Hastanesi"
    assert project.source == "project_field"
    assert project.page == 1
    assert equipment.unique_ids() == ("HKS-12",)
    assert equipment.equipment_ids[0].equipment_id == "HKS-12"
    assert equipment.equipment_ids[0].source == "unit_reference"


def test_pdf1_unit_reference_does_not_capture_revision_text():
    pages = [
        "Project Ekol Sada Hastanesi\n"
        "Unit Reference HKS-12 Revision No\n"
        "Designer Sample 3"
    ]

    equipment = discover_pdf1_unit_reference(pages)

    assert equipment.unique_ids() == ("HKS-12",)
    assert all("REVISION" not in item.equipment_id.upper() for item in equipment.equipment_ids)


def test_pdf1_unit_reference_supports_ks_ids_with_dot_and_underscore():
    pages = [
        "Project Ekol Sada Hastanesi\n"
        "Unit Reference KS-00.02 Revision No\n"
        "Unit Reference KS_01.03 Revision No"
    ]

    equipment = discover_pdf1_unit_reference(pages)

    assert equipment.unique_ids() == ("KS-00.02", "KS-01.03")
