from coordinate_motor_discovery import (
    _DIRECTION_RECT,
    _SELECTION_CURRENT_RECT,
    _SELECTION_MODEL_RECT,
    compare_motor_model_lists,
    discover_selection_motor_models,
    expand_model_quantity,
    parse_selection_motor_model,
)
from motor_fuse_matching import (
    FUSE_CURRENT_RANGES,
    check_fuse_current,
    expected_fuse_rating,
    parse_fuse_rating,
)
from stage2_pdf_discovery import (
    _MOTOR_FUSE_BOX,
    _MOTOR_MODEL_BOXES,
    _SINGLE_MOTOR_FUSE_BOX,
    discover_coordinate_pdf2_motor_fuses,
    discover_coordinate_pdf2_motor_models,
    motor_fuse_box_for_fan_count,
)


def test_selection_motor_model_parses_supply_and_exhaust_models_and_quantity():
    text = "8300100068- VBH0500CTTRS/L / 2x2"

    result = parse_selection_motor_model(text, "Supply air", 6)

    assert result is not None
    assert result.component_role == "supply_fan"
    assert result.model == "VBH0500CTTRS/L"
    assert result.quantity == "2x2"
    assert len(expand_model_quantity(result)) == 4

    exhaust = parse_selection_motor_model(
        "Supplier / Model / Quantity in WxH VBH0450CTRNS/S / 1x1",
        "Exhaust air",
        10,
    )
    assert exhaust is not None
    assert exhaust.component_role == "exhaust_fan"
    assert exhaust.model == "VBH0450CTRNS/S"


def test_selection_model_uses_top_box_line_not_supplier_reference_below():
    ziehl = parse_selection_motor_model(
        "GR31I-ZID.DC.CR -\n186637/A01 / 1x1",
        "Supply air",
        model_lines=("GR31I-ZID.DC.CR -", "186637/A01 / 1x1"),
    )
    ebm = parse_selection_motor_model(
        "K3G450-PA31-61 FAN (EBM)\n/ 2x1",
        "Exhaust air",
        model_lines=("K3G450-PA31-61 FAN (EBM)", "/ 2x1"),
    )

    assert (ziehl.model, ziehl.quantity) == ("GR31I-ZID.DC.CR", "1x1")
    assert (ebm.model, ebm.quantity) == ("K3G450-PA31-61", "2x1")


def test_selection_model_skips_leading_supplier_code_on_model_line():
    result = parse_selection_motor_model(
        "8300100068- VBH0500CTTRS/L\n186637/A01 / 2x2",
        "Supply air",
        model_lines=("8300100068- VBH0500CTTRS/L", "186637/A01 / 2x2"),
    )

    assert result.model == "VBH0500CTTRS/L"
    assert result.quantity == "2x2"


def test_selection_motor_models_read_direction_and_model_from_configured_boxes(monkeypatch):
    class FakePage:
        def __init__(self, text):
            self.text = text

        def get_text(self, kind):
            assert kind == "text"
            return self.text

    pages = [
        FakePage("Plug fan Supply air"),
        FakePage("Plug fan Exhaust air"),
        FakePage("Heating coil"),
    ]
    box_values = {
        (0, _DIRECTION_RECT): "Supply air",
        (0, _SELECTION_MODEL_RECT): "8300100068- VBH0500CTTRS/L / 2x2",
        (0, _SELECTION_CURRENT_RECT): "9,60",
        (1, _DIRECTION_RECT): "Exhaust air",
        (1, _SELECTION_MODEL_RECT): "8300100069- VBH0450CTRNS/S / 1x1",
        (1, _SELECTION_CURRENT_RECT): "7.25",
    }
    calls = []

    def read_box(page, box):
        page_number = pages.index(page)
        calls.append((page_number, box))
        return box_values.get((page_number, box), "")

    monkeypatch.setattr("coordinate_motor_discovery._rect_text", read_box)
    results = discover_selection_motor_models(document=pages)

    assert [(r.page_number, r.component_role, r.model, r.quantity, r.current) for r in results] == [
        (1, "supply_fan", "VBH0500CTTRS/L", "2x2", "9,60"),
        (2, "exhaust_fan", "VBH0450CTRNS/S", "1x1", "7.25"),
    ]
    assert calls == [
        (0, _DIRECTION_RECT),
        (0, _SELECTION_MODEL_RECT),
        (0, _SELECTION_CURRENT_RECT),
        (1, _DIRECTION_RECT),
        (1, _SELECTION_MODEL_RECT),
        (1, _SELECTION_CURRENT_RECT),
    ]


def test_supply_only_selection_contains_no_exhaust_fan_result(monkeypatch):
    class FakePage:
        def get_text(self, kind):
            assert kind == "text"
            return "Plug fan Supply air"

    values = {
        _DIRECTION_RECT: "Supply air",
        _SELECTION_MODEL_RECT: "8300100068- VBH0500CTTRS/L / 2x2",
        _SELECTION_CURRENT_RECT: "9,60",
    }
    monkeypatch.setattr(
        "coordinate_motor_discovery._rect_text",
        lambda _page, box: values.get(box, ""),
    )

    results = discover_selection_motor_models(document=[FakePage()])

    assert [result.component_role for result in results] == ["supply_fan"]


def test_selection_falls_back_to_type_row_and_rated_current_text(monkeypatch):
    class FakePage:
        def get_text(self, kind):
            assert kind == "text"
            return (
                "Plug fan Supply air Section length [mm] 941,0 "
                "Type K3G450-PA31-61 FAN (EBM) Model Brand "
                "Supplier / Model / Quantity in WxH / 2x1 "
                "Motor Full Load Efficiency [%] 88,95 "
                "Rated Current [A] 6,80 Protection / Ins. & Temp. Class"
            )

    values = {
        _DIRECTION_RECT: "Supply air",
        _SELECTION_MODEL_RECT: "/ 2x1",
        _SELECTION_CURRENT_RECT: "3 ph",
    }
    monkeypatch.setattr(
        "coordinate_motor_discovery._rect_text",
        lambda _page, box: values.get(box, ""),
    )

    results = discover_selection_motor_models(document=[FakePage()])

    assert len(results) == 1
    assert results[0].model == "K3G450-PA31-61"
    assert results[0].quantity == "2x1"
    assert results[0].current == "6,80"


def test_selection_parses_type_model_when_supplier_fields_are_interleaved(monkeypatch):
    class FakePage:
        def __init__(self, text, model_text, current_text, direction):
            self.text = text
            self.model_text = model_text
            self.current_text = current_text
            self.direction = direction

        def get_text(self, kind):
            assert kind == "text"
            return self.text

    supply_page = FakePage(
        "Plug fan\nSupply air Section length [mm] 941,0\n"
        "Fan data 15.000 EC Plug Model Brand M3G150IF / 2x1\n"
        "Type EC Plug Model Brand\nSupplier / Model / Quantity in WxH\n"
        "Rated Current [A]\n10,30",
        "g K3G450-PB29-N1 FAN (EBM) / 2x1",
        ", 10,30",
        "Supply air",
    )
    exhaust_page = FakePage(
        "Plug fan\nExhaust air Section length [mm] 900,0\n"
        "Fan data 12.000 EC Plug Model Brand M3G112GA / 2x1\n"
        "Type EC Plug Model Brand\nSupplier / Model / Quantity in WxH\n"
        "Rated Current [A]\n4,40",
        "g K3G355-PV70-05 FAN (EBM) / 2x1",
        ", 4,40",
        "Exhaust air",
    )
    monkeypatch.setattr(
        "coordinate_motor_discovery._rect_text",
        lambda page, box: {
            _DIRECTION_RECT: page.direction,
            _SELECTION_MODEL_RECT: page.model_text,
            _SELECTION_CURRENT_RECT: page.current_text,
        }[box],
    )

    results = discover_selection_motor_models(
        document=[supply_page, exhaust_page]
    )

    assert [
        (result.component_role, result.model, result.quantity, result.current)
        for result in results
    ] == [
        ("supply_fan", "K3G450-PB29-N1", "2x1", "10,30"),
        ("exhaust_fan", "K3G355-PV70-05", "2x1", "4,40"),
    ]


def test_model_lists_compare_case_and_separator_insensitively_but_keep_counts():
    assert compare_motor_model_lists(
        ["VBH0500CTTRS/L"] * 2,
        ["vbh0500cttrsl", "VBH0500CTTRS-L"],
    ) == "MODEL EŞLEŞTİ"
    assert compare_motor_model_lists(
        ["VBH0500CTTRS/L"] * 2,
        ["VBH0500CTTRS/L"],
    ) == "MODEL UYUŞMAZ"


def test_fuse_current_bands_and_boundaries():
    assert [
        (item.rating_a, item.minimum_current_a, item.maximum_current_a)
        for item in FUSE_CURRENT_RANGES
    ] == [
        (10, 0.0, 7.0),
        (16, 7.0, 13.0),
        (20, 13.0, 16.0),
        (25, 16.0, 20.0),
        (32, 20.0, 26.0),
        (40, 26.0, 32.0),
    ]
    assert expected_fuse_rating(5.9) == 10
    assert expected_fuse_rating(7) == 16
    assert expected_fuse_rating(13) == 20
    assert expected_fuse_rating(32) == 40
    assert expected_fuse_rating(32.1) is None


def test_fuse_check_accepts_only_the_current_band_rating():
    assert check_fuse_current("5,9 A", "10 A").status == "MATCH"
    assert check_fuse_current("5.9", "16A").status == "MISMATCH"
    assert check_fuse_current("5.9", "6 A").status == "MISMATCH"
    assert check_fuse_current(None, "10 A").status == "UNKNOWN"
    assert parse_fuse_rating("3x10A") == 10
    assert check_fuse_current("5.9", "6A").status == "MISMATCH"


def test_pdf2_model_scan_checks_both_boxes_on_each_matching_connection_page(monkeypatch):
    class FakePage:
        def __init__(self, title):
            self.title = title

        def get_text(self, kind):
            assert kind == "text"
            return self.title

    pages = [
        FakePage("Supply Motor Connections-1"),
        FakePage("Supply Motor Connections-1"),
        FakePage("Return Motor Connections-1"),
        FakePage("Other page"),
    ]
    values = {
        (1, _MOTOR_MODEL_BOXES[0]): "VBH0500CTTRS/L",
        (1, _MOTOR_MODEL_BOXES[1]): "VBH0500CTTRS/L",
        (2, _MOTOR_MODEL_BOXES[0]): "VBH0500CTTRS/L",
        (3, _MOTOR_MODEL_BOXES[1]): "VBH0450CTRNS/S",
    }
    calls = []

    def read_box(page, box):
        page_number = pages.index(page) + 1
        calls.append((page_number, box))
        return values.get((page_number, box), "")

    monkeypatch.setattr("stage2_pdf_discovery._coordinate_text_in_box", read_box)
    results = discover_coordinate_pdf2_motor_models(pages)

    assert [(r.page_number, r.component_role, r.model) for r in results] == [
        (1, "supply_fan", "VBH0500CTTRS/L"),
        (1, "supply_fan", "VBH0500CTTRS/L"),
        (2, "supply_fan", "VBH0500CTTRS/L"),
        (3, "exhaust_fan", "VBH0450CTRNS/S"),
    ]
    assert len(calls) == 6
    assert all(box in _MOTOR_MODEL_BOXES for _, box in calls)


def test_pdf2_fuse_scan_reads_only_the_fuse_box_on_every_supply_and_return_sheet(monkeypatch):
    class FakePage:
        def __init__(self, title):
            self.title = title

        def get_text(self, kind):
            assert kind == "text"
            return self.title

    pages = [
        FakePage("Supply Motor Connections-1"),
        FakePage("Supply Motor Connections-1"),
        FakePage("Return Motor Connections-1"),
        FakePage("Other page 32A"),
    ]
    values = {
        (1, _MOTOR_FUSE_BOX): "3x10A 400V other label",
        (2, _SINGLE_MOTOR_FUSE_BOX): "text 16A",
        (3, _MOTOR_FUSE_BOX): "text 6A and other values",
    }
    calls = []

    def read_box(page, box):
        page_number = pages.index(page) + 1
        calls.append((page_number, box))
        return values.get((page_number, box), "")

    monkeypatch.setattr("stage2_pdf_discovery._coordinate_text_in_box", read_box)
    results = discover_coordinate_pdf2_motor_fuses(pages)

    assert [
        (
            result.source_page,
            result.component_role,
            result.fuse_rating_a,
            result.pole_count,
            result.coordinate_box,
        )
        for result in results
    ] == [
        (1, "supply_fan", 10, 3, _MOTOR_FUSE_BOX),
        (2, "supply_fan", 16, None, _SINGLE_MOTOR_FUSE_BOX),
        (3, "exhaust_fan", 6, None, _MOTOR_FUSE_BOX),
    ]
    assert calls == [
        (page_number, box)
        for page_number in (1, 2, 3)
        for box in (_MOTOR_FUSE_BOX, _SINGLE_MOTOR_FUSE_BOX)
    ]


def test_single_fan_uses_alternate_electrical_fuse_coordinate(monkeypatch):
    selection_result = type(
        "SelectionMotor", (), {"quantity": "1x1", "model": "VBH0500CTTRS/L"}
    )()
    fan_count = len(expand_model_quantity(selection_result))
    assert motor_fuse_box_for_fan_count(fan_count) == _SINGLE_MOTOR_FUSE_BOX
    assert motor_fuse_box_for_fan_count(4) == _MOTOR_FUSE_BOX
