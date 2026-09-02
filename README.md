# pdf_kw_selector

Engineering PDF'lerinden **doğru kW bilgisini bulup iki farklı PDF'deki karşılığını doğrulamak** için geliştirilen aşamalı doğrulama motoru.

## v0.1.1 — Windows Test Sürümü

Bu sürümde **PDF 1 / Stage 1 masaüstü arayüzü** kullanılabilir durumdadır.

```text
PDF Seç → ANALİZ ET → Fan bölümlerini bul → Rated Power [kW]
                                      ↓
                         Supply air / Exhaust air
                                      ↓
                              1x1 / 2x1 / 3x1
                                      ↓
                     Vant 1 / Vant 2 / Asp 1...
```

`desktop_app.py` Windows'ta Tkinter ile çalışan offline test arayüzüdür. PDF 1 seçildiğinde fan teknik bloklarını arar, `Rated Power [kW]` / `Anma gücü [kW]` değerini çıkarır, Supply air / Exhaust air sınıflandırmasını gösterir ve fiziksel motor listesini ekrana getirir. Sonuç JSON olarak da kaydedilebilir.

### Gerçek Systemair PDF terminolojisi

Bu projedeki Systemair örneğinde dönüş tarafı motor/fan yönü **`Exhaust air`** olarak geçmektedir. Bu nedenle kodda:

```text
Supply air  → Vantilatör → Vant
Exhaust air → Aspiratör  → Asp
```

olarak sabitlenmiştir. `Return air` artık aspiratör yönü olarak kullanılmaz.

Örnek gerçek PDF:

```text
Page 7  — Plug fan / Supply air
Rated Power [kW] 22,000 x (2x1)
→ Vant 1 = 22 kW
→ Vant 2 = 22 kW

Page 10 — Plug fan / Exhaust air
Rated Power [kW] 15,000 x (2x1)
→ Asp 1 = 15 kW
→ Asp 2 = 15 kW
```

Bu değerler PDF'nin kendi teknik tablolarındaki `Rated Power [kW]` satırlarından alınır; `shaft power` ve `Tot. Abs. power` gibi diğer güç alanları motor gücü yerine seçilmez.

Windows EXE build workflow'u `PDF_KW_Selector_v0.1.1.exe` üretir.

> v0.1.1 yalnızca PDF 1 / Stage 1 testidir. PDF 2 karşılaştırması sonraki sürümde aktif edilecektir.

---

## Ana hedef

Sisteme iki PDF verilir. Sistem kW değerlerini doğrudan tüm PDF'den toplamaz ve ilk bulduğu kW değerini karşılaştırmaz.

```text
PDF 1
  ↓
AŞAMA 1 — doğru sayfa + ekipman + komponent + motor listesi
  ↓
AŞAMA 2 — PDF 2'de karşılık gelen motor listesi
  ↓
AŞAMA 3 — DATABASE ÜZERİNDEN KARŞILAŞTIR
  ↓
MATCH / MISMATCH / NOT_FOUND / AMBIGUOUS / REVIEW_REQUIRED
```

## Motor sınıflandırma

```text
Supply air  → Vantilatör → Vant
Exhaust air → Aspiratör  → Asp
```

`Return air` tek başına aspiratör yönü olarak kabul edilmez. Sistemair örneğinde gerçek fan bloğu `Exhaust air` başlığı altında yer almaktadır.

## Motor sayısı

```text
1x1 → 1 motor
2x1 → 2 motor
3x1 → 3 motor
```

Örneğin `Supply air + 2x1` → `Vant 1`, `Vant 2`; `Exhaust air + 3x1` → `Asp 1`, `Asp 2`, `Asp 3`.

## Database

Normalize edilmiş fiziksel motor kayıtları lokal SQLite database'de tutulur:

```text
motors
────────────────────────────────────────────
equipment_id | equipment_type | component_type
component_index | component_label | power_kw
source_group | motor_count | source_page | confidence
```

Karşılaştırma ileride ham PDF metni üzerinden değil, iki normalize database üzerinden yapılacaktır.

---

# AŞAMA 1 — PDF 1

1. PDF'nin bütün sayfaları taranır.
2. Motor/fan teknik blokları puanlanır.
3. `Rated Power [kW]` / `Anma gücü [kW]` alanı aranır.
4. `Supply air` → Vantilatör, `Exhaust air` → Aspiratör.
5. `1x1 / 2x1 / 3x1` fiziksel motor kayıtlarına genişletilir.
6. Her fiziksel motor database'e ayrı kayıt olarak yazılır.

Gerçek Systemair test PDF'sindeki hedef:

```text
Page 7:
Supply air + Rated Power [kW] 22,000 x (2x1)
→ Vant 1 = 22.0 kW
→ Vant 2 = 22.0 kW

Page 10:
Exhaust air + Rated Power [kW] 15,000 x (2x1)
→ Asp 1 = 15.0 kW
→ Asp 2 = 15.0 kW
```

`Shaft Power`, `Tot. Abs. power, excluding VSD`, `Tot. Abs. power, including VSD` gibi diğer kW alanları `Rated Power` yerine seçilmez.

---

# MEVCUT KOD

- `stage1_page_discovery.py` → PDF 1 fan bölümü + rated motor power keşfi.
- `motor_database.py` → motor gruplarını fiziksel motor kayıtlarına genişletir.
- `local_database.py` → lokal SQLite depolama.
- `desktop_app.py` → v0.1.1 masaüstü test arayüzü.
- `.github/workflows/build-windows.yml` → Windows EXE üretimi.
- `tests/test_stage1.py` → Supply/Exhaust regression testleri.

---

# GELİŞTİRME SIRASI

## Faz 1 — PDF 1

- [x] `Rated Power [kW]` / `Anma gücü [kW]` hedefleme
- [x] doğru sayfa puanlama
- [x] `1x1 / 2x1 / 3x1`
- [x] fiziksel motor kayıtları
- [x] SQLite database modeli
- [x] Supply air → Vantilatör
- [x] Exhaust air → Aspiratör
- [x] Return air'in aspiratör yönü olarak kaldırılması
- [x] Supply + Exhaust fanlarını aynı PDF'de ayrı keşfetme
- [x] Windows masaüstü test arayüzü
- [x] Windows EXE build workflow
- [ ] gerçek PDF'den daha fazla fan/komponent varyasyonunu otomatik keşfet
- [ ] PDF 1 database'ini tamamen doldur

## Faz 2 — PDF 2

- [ ] PDF 1 database kayıtlarını hedef al
- [ ] PDF 2'de aynı ekipmanları bul
- [ ] komponentleri bul
- [ ] motor indekslerini eşleştir
- [ ] PDF 2 database'ini oluştur

## Faz 3 — Karşılaştırma

- [ ] database karşılaştırma
- [ ] MATCH / MISMATCH
- [ ] NOT_FOUND / AMBIGUOUS / REVIEW_REQUIRED
- [ ] tolerans
- [ ] kaynak sayfaları
