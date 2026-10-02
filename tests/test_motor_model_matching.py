from coordinate_motor_discovery import (
    compare_motor_model_lists,
    expand_model_quantity,
    parse_selection_motor_model,
)
from stage2_pdf_discovery import (
    _MOTOR_MODEL_BOXES,
    discover_coordinate_pdf2_motor_models,
)


def test_selection_motor_model_parses_supply_and_exhaust_models_and_quantity():
    text = (
        "Plug fan Supply air Supplier / Model / Quantity in WxH "
        "VBH0500CTTRS/L / 2x2"
    )

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
