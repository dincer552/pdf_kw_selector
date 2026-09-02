from stage1_page_discovery import (
    build_stage1_motor_records,
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

REALISTIC_SUPPLY = """
Project 155-Atlas Teleferik
Unit Reference PW-02
Plug fan Supply air Section length [mm] 1,071.0 Pressure drop [Pa]
Fan data Motor data
Model / Quantity in WxH Std-IE3-50-90-2-2.2 / 1x1
Rated Power [kW] 2.200 x (1x1)
Tot. Abs. power,excluding VSD [kW] 1.6063
"""

REALISTIC_EXHAUST = """
Project 155-Atlas Teleferik
Unit Reference PW-02
Plug fan Exhaust air Section length [mm] 1,071.0 Pressure drop [Pa]
Fan data Motor data
Model / Quantity in WxH Std-IE3-50-80-2-1.1 / 1x1
Rated Power [kW] 1.100 x (1x1)
Tot. Abs. power,excluding VSD [kW] 0.8468
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


def test_realistic_pw02_supply_page_creates_physical_motor():
    result = extract_rated_motor_power_from_page(REALISTIC_SUPPLY, page_number=6)
    assert result is not None
    assert result.value_kw == 2.2
    assert result.quantity == "1x1"
    assert result.equipment_id == "PW2"
    assert result.component_type == "Vantilatör"
    records = build_stage1_motor_records(result)
    assert len(records) == 1
    assert records[0].component_label == "Vant 1"
    assert records[0].power_kw == 2.2


def test_realistic_pw02_exhaust_page_creates_physical_motor():
    result = extract_rated_motor_power_from_page(REALISTIC_EXHAUST, page_number=8)
    assert result is not None
    assert result.value_kw == 1.1
    assert result.quantity == "1x1"
    assert result.equipment_id == "PW2"
    assert result.component_type == "Aspiratör"
    records = build_stage1_motor_records(result)
    assert len(records) == 1
    assert records[0].component_label == "Asp 1"
    assert records[0].power_kw == 1.1


def test_page_number_is_not_hardcoded_for_motor_discovery():
    pages = ["cover page", "unrelated 10 kW", REALISTIC_EXHAUST, "unrelated page"]
    results = [
        extract_rated_motor_power_from_page(text, page_number=index)
        for index, text in enumerate(pages, start=1)
    ]
    found = [item for item in results if item is not None]
    assert len(found) == 1
    assert found[0].page_number == 3
    assert found[0].value_kw == 1.1
