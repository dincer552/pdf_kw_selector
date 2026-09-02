from pathlib import Path

from stage1_page_discovery import (
    detect_component_type,
    discover_motor_power_page,
    extract_rated_motor_power_from_page,
    find_rated_motor_power_in_pdf,
)

PDF_SAMPLE = Path("tests/data/AHU-1_secim.pdf")


def test_exact_rated_power_line_is_extracted():
    text = "Motor Data Supply air Anma gücü [kW] 3,000 x (1x1) Shaft Power [kW] 2,090"
    result = extract_rated_motor_power_from_page(text, 6)
    assert result is not None
    assert result.page_number == 6
    assert result.value_kw == 3.0
    assert result.raw_value == "3,000"
    assert result.quantity == "1x1"
    assert result.field == "fan_motor_power"
    assert result.component_type == "Vantilatör"
    assert result.component_role == "supply_fan"


def test_supply_air_maps_to_vantilator():
    assert detect_component_type("Plug fan Supply air") == ("Vantilatör", "supply_fan")


def test_return_air_maps_to_aspirator():
    assert detect_component_type("Plug fan Return air") == ("Aspiratör", "return_fan")


def test_quantity_spacing_and_multiplication_symbol_are_normalized():
    result = extract_rated_motor_power_from_page(
        "Motor Data Supply air Anma gücü [kW]: 3.000 x ( 1 × 1 )", 6
    )
    assert result is not None
    assert result.value_kw == 3.0
    assert result.quantity == "1x1"


def test_rated_power_without_quantity_is_supported():
    result = extract_rated_motor_power_from_page("Motor Data Anma gücü [kW] 7,500 Nominal RPM 2900", 4)
    assert result is not None
    assert result.value_kw == 7.5
    assert result.quantity is None


def test_nearby_other_kw_values_are_not_selected():
    text = (
        "Cooling Capacity 44,63 [kW] Shaft Power [kW] 2,090 "
        "Tot. abs. güç, VSD hariç [kW] 2,3998 Tot. abs. VSD dahil güç [kW] 2,474"
    )
    assert extract_rated_motor_power_from_page(text, 6) is None


def test_anma_akimi_is_not_confused_with_anma_gucu():
    assert extract_rated_motor_power_from_page("Anma akımı [A] 5,77", 6) is None


def test_page_6_ranks_above_other_pages():
    pages = [
        "AHU-1 Fan Motor Power / Nominal Rpm 3 [kW]",
        "Ecodesign Enerji Sınıfı İçin Emilen Motor Gücü 2,418 [kW]",
        "Geometrical drawing",
        "Filter Supply air",
        "Cooling Capacity 44,63 [kW] Heating Capacity 58,37 [kW]",
        "Plug fan Fan Data Motor Data Supply air Anma gücü [kW] 3,000 x (1x1) Shaft Power [kW] 2,090",
    ]
    ranked = discover_motor_power_page(pages)
    assert ranked[0].page_number == 6


def test_real_sample_pdf_returns_3kw_on_page_6():
    if not PDF_SAMPLE.exists():
        return
    result = find_rated_motor_power_in_pdf(PDF_SAMPLE)
    assert result is not None
    assert result.page_number == 6
    assert result.value_kw == 3.0
    assert result.raw_value == "3,000"
    assert result.quantity == "1x1"
