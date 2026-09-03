# pdf_kw_selector

Engineering PDF'lerinden **doğru motor anma gücünü (kW) bulup fiziksel motor bazında normalize eden ve iki PDF arasında doğrulayan** motor.

## Güncel akış — v0.3.1

```text
PDF 1 — Seçim / Referans
        ↓
Doğru fan bloğunu ve Rated Power / Anma gücünü bul
        ↓
1x1 / 2x1 / 3x1 → fiziksel motor database
        ↓
PDF 2 — Elektrik / Sipariş
        ↓
Supply / Return / Exhaust Motor Connections sayfalarını bul
        ↓
Motorun elektrik çizimindeki kW değerini bul
        ↓
1x1 / 2x1 / 3x1 → PDF 2 fiziksel motor database
        ↓
PDF 1 ↔ PDF 2 aynı ekipman + komponent + motor index
        ↓
MATCH / MISMATCH / ONLY_IN_PDF1 / ONLY_IN_PDF2
```

## Motor mantığı

```text
Supply air  → Vantilatör → Vant
Return air  → Aspiratör  → Asp
Exhaust air → Aspiratör  → Asp

1x1 → 1 fiziksel motor
2x1 → 2 fiziksel motor
3x1 → 3 fiziksel motor
```

Örneğin:

```text
PDF 1:
Rated Power [kW] 22,000 x (2x1)
→ Vant 1 = 22.0 kW
→ Vant 2 = 22.0 kW

PDF 2:
Supply Motor Connections-1 → 22.0 kW
ve özet quantity 2x1 ise
→ Vant 1 = 22.0 kW
→ Vant 2 = 22.0 kW
```

## PDF 2 motor gücü keşfi

PDF 2 elektrik/sipariş çizimlerinde motor gücü öncelikle **özel motor bağlantı sayfasından** alınır. Örneğin:

```text
Supply Motor Connections-1
400 / 3Ph / 50Hz
7,5 kW 3~
```

→ `Supply` → `Vantilatör` → `Vant` → `7.5 kW`

```text
Return Motor Connections-1
400 / 3Ph / 50Hz
5,5 kW 3~
```

→ `Return` → `Aspiratör` → `Asp` → `5.5 kW`

Title Page'deki fan motor güçleri quantity bilgisi için fallback olarak kullanılabilir; aynı motorun bağlantı sayfası varsa bağlantı sayfasındaki elektriksel motor değeri tercih edilir.

## Kritik kural

Karşılaştırmanın hedefi **motor Rated Power / Anma gücü**dür.

Şunlar motor gücü olarak kullanılmaz:

- Unit Total Power
- Cooling Capacity
- Heating Capacity
- Shaft Power
- VSD dahil / hariç toplam güç
- Motorla ilgisiz diğer kW değerleri

## Fiziksel motor karşılaştırması

Her motor için ana anahtar:

```text
ekipman + komponent tipi + fiziksel motor index
```

Örnek:

```text
AHU-EF-01 + Vantilatör + 1 → Vant 1
AHU-EF-01 + Aspiratör  + 1 → Asp 1
```

Sonuçlar:

- `MATCH` — kW farkı tolerans içinde
- `MISMATCH` — kW farkı tolerans dışında
- `ONLY_IN_PDF1` — motor yalnız PDF 1'de bulundu
- `ONLY_IN_PDF2` — motor yalnız PDF 2'de bulundu

Varsayılan karşılaştırma toleransı `0.01 kW`.

## Mevcut modüller

- `stage1_page_discovery.py` — PDF 1 doğru fan bloğu/sayfa ve Rated Power keşfi.
- `motor_database.py` — motor grubunu fiziksel motor kayıtlarına genişletir.
- `stage2_pdf_discovery.py` — PDF 2 elektrik motor bağlantı sayfalarından motor kW keşfi.
- `motor_compare.py` — iki fiziksel motor database'ini motor bazında karşılaştırır.
- `kw_compare.py` — genel/semantik kW alan karşılaştırma yardımcıları.
- `pdf_kw_selector.py` — bağlam duyarlı kW adayı seçimi.
- `desktop_app.py` — PDF 1 + PDF 2 seçim, analiz ve karşılaştırma arayüzü.
- `tests/test_stage2.py` — PDF 2 bağlantı sayfası, quantity expansion ve karşılaştırma testleri.
- `.github/workflows/build-windows.yml` — testler başarılıysa Windows EXE üretir.

## Test hedefi

```text
pytest -q
↓
Tüm testler PASS
↓
PyInstaller
↓
PDF_KW_Selector_v0.3.1.exe
```

## Sonraki geliştirme

1. Gerçek PDF çiftlerinden daha fazla PDF 2 formatı toplamak.
2. Motor bağlantı sayfası varyasyonlarını genişletmek.
3. `AMBIGUOUS / REVIEW_REQUIRED` durumlarını motor bazında eklemek.
4. Karşılaştırma ekranında kaynak metni ve sayfayı daha görünür hale getirmek.
