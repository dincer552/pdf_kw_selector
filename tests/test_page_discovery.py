from stage1_page_discovery import (
    discover_motor_power_page,
    extract_rated_motor_power_from_page,
)


PAGE_1 = """
Project YAS BOYA TESISI
Birim Referansı AHU-1
Fan Motor Power / Nominal Rpm 3 [kW] (1x1) / 2900 [1/min]
Cooling Capacity 44.63 [kW]
"""

PAGE_2 = """
Ecodesign - Teknik Veriler
Enerji Sınıfı İçin Emilen Motor Gücü, VSD Dahil 2,418 [kW]
"""

PAGE_6 = """
Birim Referansı AHU-1
Plug fan Supply air
Fan Data Motor Data
Model / Miktar Std-IE3-50-100-2-3 / 1x1
Anma gücü [kW] 3,000 x (1x1)
Nominal RPM [1/min] 2.900
Tot. abs. güç, VSD hariç [kW] 2,3998
Tot. abs. VSD dahil güç [kW] 2,474
Shaft Power [kW] 2,090
"""


def test_page_6_wins_for_explicit_rated_motor_power():
    ranked = discover_motor_power_page([PAGE_1, PAGE_2, PAGE_6])
    assert ranked[0].page_number == 3
    assert "explicit rated power" in ranked[0].matched_terms


def test_extract_exact_anma_gucu_value_and_quantity():
    result = extract_rated_motor_power_from_page(PAGE_6, page_number=6)
    assert result is not None
    assert result.page_number == 6
    assert result.value_kw == 3.0
    assert result.raw_value == "3,000"
    assert result.quantity == "1x1"
    assert result.field == "fan_motor_power"
    assert result.confidence == "high"


def test_unrelated_kw_values_are_not_selected_as_rated_power():
    result = extract_rated_motor_power_from_page(
        "Cooling Capacity 44.63 [kW]\nShaft Power [kW] 2,090\nTot. abs. güç, VSD hariç [kW] 2,3998",
        page_number=5,
    )
    assert result is None


def test_return_air_maps_to_aspirator():
    from stage1_page_discovery import detect_component_type

    assert detect_component_type("Plug fan Return air Rated Power [kW] 15,000 x (2x1)") == (
        "Aspiratör", "return_fan"
    )
