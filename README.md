# pdf_kw_selector

Engineering PDF'lerinden istenen güç değerini **bağlamına göre** seçmek için ilk sürüm.

## Amaç

Örneğin aynı PDF içinde:

- `Fan Motor: 3 kW`
- `Unit Total Power: 4 kW`
- `Total Heating: 20 kW`

gibi birden fazla değer varsa, sadece sayısal yakınlığa bakıp `4 kW` seçmek yerine fan motoruna ait `3 kW` değerini seçmek.

Ayrıca ekipman isimleri farklı yazımlarda normalize edilir:

- `AHU-1`
- `AHU_01`
- `AHU 001`

→ `AHU1`

## Kurulum

```bash
pip install -r requirements.txt
```

## Kullanım

```python
from pdf_kw_selector import select_fan_motor_power_from_pdf

result = select_fan_motor_power_from_pdf("AHU-1.pdf")

if result:
    print(result.value_kw)
    print(result.context)
```

Komut satırı:

```bash
python pdf_kw_selector.py AHU-1.pdf
```

## Test

```bash
pytest -q
```

## Tasarım ilkesi

Bu proje "PDF'deki ilk kW değerini bul" mantığı kullanmaz. Önce adayları çıkarır, her adayın çevresindeki metni değerlendirir ve toplam/aggregate alanlarını cezalandırır. Böylece sonraki aşamada fan, heater, cooling coil, electrical load vb. alanlar için ayrı seçim kuralları eklenebilir.

## Sonraki aşama

1. PDF layout/tablo konumlarını hesaba katmak.
2. Aynı ekipmana ait satır/kolon bağlamını korumak.
3. Türkçe/İngilizce teknik terim sözlüğü eklemek.
4. Birden fazla fan için sonuçları ekipman ID'siyle eşlemek.
5. Gerçek AHU PDF'leriyle regresyon test seti oluşturmak.
