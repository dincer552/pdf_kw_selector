from pathlib import Path

from stage1_page_discovery import (
    discover_motor_power_page,
    extract_rated_motor_power_from_page,
    find_rated_motor_power_in_pdf,
)


# The real PDF can be copied here for an offline regression test.
PDF_SAMPLE = Path("tests/data/AHU-1_secim.pdf")


def test_exact_rated_power_line_is_extracted():
    text = "Motor Data Anma gücü [kW] 3,000 x (1x1) Shaft Power [kW] 2,090"
    result = extract_rated_motor_power_from_page(text, 6)

    assert result is not None
    assert result.page_number == 6
    assert result.value_kw == 3.0
    assert result.raw_value == "3,000"
    assert result.quantity == "1x1"
    assert result.field == "fan_motor_power"
    assert result.confidence == "high"


def test_quantity_spacing_and_multiplication_symbol_are_normalized():
    text = "Motor Data Anma gücü [kW]: 3.000 x ( 1 × 1 )"
    result = extract_rated_motor_power_from_page(text, 6)

    assert result is not None
    assert result.value_kw == 3.0
    assert result.quantity == "1x1"


def test_rated_power_without_quantity_is_supported():
    text = "Motor Data Anma gücü [kW] 7,500 Nominal RPM 2900"
    result = extract_rated_motor_power_from_page(text, 4)

    assert result is not None
    assert result.value_kw == 7.5
    assert result.quantity is None


def test_nearby_other_kw_values_are_not_selected():
    text = (
        "Cooling Capacity 44,63 [kW] "
        "Shaft Power [kW] 2,090 "
        "Tot. abs. güç, VSD hariç [kW] 2,3998 "
        "Tot. abs. VSD dahil güç [kW] 2,474 "
        "Unit Total Power 4 kW"
    )
    assert extract_rated_motor_power_from_page(text, 6) is None


def test_anma_akimi_is_not_confused_with_anma_gucu():
    text = "Anma akımı [A] 5,77 Koruma IP55 / F"
    assert extract_rated_motor_power_from_page(text, 6) is None


def test_page_6_ranks_above_other_pages():
    pages = [
        "AHU-1 Fan Motor Power / Nominal Rpm 3 [kW]",
        "Ecodesign Enerji Sınıfı İçin Emilen Motor Gücü 2,418 [kW]",
        "Geometrical drawing",
        "Filter Supply air",
        "Cooling Capacity 44,63 [kW] Heating Capacity 58,37 [kW]",
        "Plug fan Fan Data Motor Data Anma gücü [kW] 3,000 x (1x1) Shaft Power [kW] 2,090",
    ]
    ranked = discover_motor_power_page(pages)
    assert ranked[0].page_number == 6
    assert ranked[0].score > ranked[1].score


def test_real_sample_pdf_returns_3kw_on_page_6():
    if not PDF_SAMPLE.exists():
        return

    result = find_rated_motor_power_in_pdf(PDF_SAMPLE)
    assert result is not None
    assert result.page_number == 6
    assert result.value_kw == 3.0
    assert result.raw_value == "3,000"
    assert result.quantity == "1x1"
