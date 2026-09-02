# pdf_kw_selector

Engineering PDF'lerinden güç değerlerini **alan + ekipman + satır bağlamı** ile seçip iki PDF arasında doğrulamak için geliştirilen araç.

## Ne yapıyor?

Aynı PDF içinde birden fazla kW değeri bulunabilir. Örneğin:

- `Fan Motor: 3 kW`
- `Unit Total Power: 4 kW`
- `Cooling Capacity: 44.63 kW`

Araç bunları yalnızca sayı olarak karşılaştırmaz. Değerin ait olduğu teknik alanı belirler.

Örneğin:

`AHU-1 / Supply Fan Motor Power / 3 kW`

ile:

`AHU_01 / Motor Gücü / 3,000 kW`

aynı ekipman ve aynı alan olarak normalize edilerek **MATCH** sonucuna ulaşır.

`Unit Total Power: 4 kW` ise fan motor gücü olarak yanlış eşleştirilmez.

## Mevcut yapı

- `pdf_kw_selector.py` — temel kW aday seçici ve ekipman ID normalizasyonu
- `kw_compare.py` — iki PDF'deki semantik güç alanlarını eşleştirip karşılaştırır
- `app.py` — komut satırı arayüzü
- `tests/` — regresyon testleri
- `requirements.txt` — Python bağımlılıkları

## Kurulum

```bash
pip install -r requirements.txt
```

## İki PDF'yi karşılaştırma

```bash
python app.py "AHU-1.pdf" "AHU_01.pdf"
```

Örnek çıktı:

```text
PDF kW DOĞRULAMA
========================================================================
✓ AHU1         fan_motor_power          3 kW  ↔  3 kW       MATCH
⚠ AHU1         unit_total_power         4 kW  ↔  4 kW       MATCH
```

Makine tarafından okunabilir JSON:

```bash
python app.py "AHU-1.pdf" "AHU_01.pdf" --json
```

Tolerans değiştirme:

```bash
python app.py "AHU-1.pdf" "AHU_01.pdf" --tolerance 0.05
```

## Test

```bash
pytest -q
```

## Mimari hedef

```text
PDF A ──┐
        ├─► PDF Text/Layout Extraction
PDF B ──┘
                 │
                 ▼
        Equipment Normalization
                 │
                 ▼
          Field Classification
                 │
                 ▼
          Power Value Extraction
                 │
                 ▼
          Equipment + Field Match
                 │
                 ▼
             Validation
                 │
                 ▼
          MATCH / MISMATCH / MISSING
```

## Sonraki aşamalar

1. PDF koordinat/layout bilgisini kullanmak.
2. Tablo satır ve kolon ilişkisini korumak.
3. Türkçe/İngilizce teknik terim sözlüğünü genişletmek.
4. Birden fazla fan/motoru aynı ekipman içinde ayrı ayrı eşlemek.
5. Taranmış PDF'ler için OCR katmanı eklemek.
6. Gerçek proje PDF'lerinden regresyon test seti oluşturmak.
7. Sonuçları web arayüzünde iki PDF + renkli doğrulama tablosu olarak göstermek.
