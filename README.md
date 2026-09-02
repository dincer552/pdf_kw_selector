# pdf_kw_selector

Engineering PDF'lerinden **doğru kW bilgisini bulup iki farklı PDF'deki karşılığını doğrulamak** için geliştirilen aşamalı doğrulama motoru.

## v0.1.0 — Windows Test Sürümü

Bu sürümde **PDF 1 / Stage 1 masaüstü arayüzü** kullanılabilir durumdadır.

```text
PDF Seç → ANALİZ ET → Doğru Sayfa → Anma gücü [kW]
                         ↓
                 Supply / Return
                         ↓
                    1x1 / 2x1 / 3x1
                         ↓
              Vant 1 / Vant 2 / Asp 1...
```

`desktop_app.py` Windows'ta Tkinter ile çalışan offline test arayüzüdür. PDF 1 seçildiğinde doğru teknik sayfayı arar, `Anma gücü [kW]` değerini çıkarır, Supply air / Return air sınıflandırmasını gösterir ve fiziksel motor listesini ekrana getirir. Sonuç JSON olarak da kaydedilebilir.

Windows EXE build workflow'u `PDF_KW_Selector_v0.1.0.exe` üretir.

> v0.1.0 yalnızca PDF 1 / Stage 1 testidir. PDF 2 karşılaştırması sonraki sürümde aktif edilecektir.

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
Supply air → Vantilatör → Vant
Return air → Aspiratör  → Asp
```

Aynı sayfada iki yön bulunursa sistem tüm sayfaya bakarak tahmin yapmaz; ilgili fan bloğunun lokal bağlamı çözülecektir.

## Motor sayısı

```text
1x1 → 1 motor
2x1 → 2 motor
3x1 → 3 motor
```

Örneğin `Supply air + 2x1` → `Vant 1`, `Vant 2`; `Return air + 3x1` → `Asp 1`, `Asp 2`, `Asp 3`.

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
3. `Anma gücü [kW]` alanı aranır.
4. `Supply air` → Vantilatör, `Return air` → Aspiratör.
5. `1x1 / 2x1 / 3x1` fiziksel motor kayıtlarına genişletilir.
6. Her motor database'e ayrı kayıt olarak yazılır.

Mevcut test PDF'sindeki hedef:

```text
Anma gücü [kW] 3,000 x (1x1)
→ 3.0 kW
→ Vant 1
```

`Shaft Power`, VSD dahil/hariç güç gibi diğer kW alanları `Anma gücü` yerine seçilmez.

---

# MEVCUT KOD

- `stage1_page_discovery.py` → PDF 1 sayfa + rated motor power keşfi.
- `motor_database.py` → motor gruplarını fiziksel motor kayıtlarına genişletir.
- `local_database.py` → lokal SQLite depolama.
- `desktop_app.py` → v0.1.0 masaüstü test arayüzü.
- `.github/workflows/build-windows.yml` → Windows EXE üretimi.

---

# GELİŞTİRME SIRASI

## Faz 1 — PDF 1

- [x] `Anma gücü [kW]` hedefleme
- [x] doğru sayfa puanlama
- [x] `1x1 / 2x1 / 3x1`
- [x] fiziksel motor kayıtları
- [x] SQLite database modeli
- [x] Supply air → Vantilatör
- [x] Return air → Aspiratör
- [x] Windows masaüstü test arayüzü
- [x] Windows EXE build workflow
- [ ] gerçek PDF'den çoklu Vant/Asp komponentlerini otomatik keşfet
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

## Faz 4 — Tam arayüz

```text
PDF 1 seç
PDF 2 seç
   ↓
PDF 1 Motor Database
   ↓
PDF 2 Motor Database
   ↓
Karşılaştırma
   ↓
Sonuç tablosu
```

## Faz 5 — Final Windows EXE

Windows'ta çift tıklayarak çalıştırılabilen final uygulama.

---

# SÜRÜMLEME

Her ana aşama gerçek PDF ile test edilir ve ayrı sürüm oluşturulur:

```text
v0.1.0 → PDF 1 masaüstü test
v0.2.0 → PDF 2 keşif
v0.3.0 → database karşılaştırma
v0.4.0 → çoklu motor / çoklu AHU
...
v1.0.0 → final
```
