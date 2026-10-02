from coordinate_motor_discovery import (
    _DIRECTION_RECT,
    _SELECTION_CURRENT_RECT,
    _SELECTION_MODEL_RECT,
    compare_motor_model_lists,
    discover_selection_motor_models,
    expand_model_quantity,
    parse_selection_motor_model,
)
from stage2_pdf_discovery import (
    _MOTOR_MODEL_BOXES,
    discover_coordinate_pdf2_motor_models,
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


def test_model_lists_compare_case_and_separator_insensitively_but_keep_counts():
    assert compare_motor_model_lists(
        ["VBH0500CTTRS/L"] * 2,
        ["vbh0500cttrsl", "VBH0500CTTRS-L"],
    ) == "MODEL EŞLEŞTİ"
    assert compare_motor_model_lists(
        ["VBH0500CTTRS/L"] * 2,
        ["VBH0500CTTRS/L"],
    ) == "MODEL UYUŞMAZ"


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
