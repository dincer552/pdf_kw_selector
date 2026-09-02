# pdf_kw_selector

Engineering PDF'lerinden **doğru kW bilgisini bulup iki farklı PDF'deki karşılığını doğrulamak** için geliştirilen aşamalı doğrulama motoru.

## v0.1.0 — Windows Test Sürümü

Bu sürümde **PDF 1 / Stage 1 masaüstü arayüzü** kullanılabilir durumdadır.

Windows'ta arayüz:

```text
PDF Seç
   ↓
ANALİZ ET
   ↓
Doğru sayfa
   ↓
Anma gücü [kW]
   ↓
Supply air / Return air
   ↓
1x1 / 2x1 / 3x1
   ↓
Vant 1 / Vant 2 / Asp 1 / ...
```

Arayüz `desktop_app.py` ile çalışır. PDF 1 seçildiğinde doğru teknik sayfayı arar, `Anma gücü [kW]` değerini çıkarır ve fiziksel motor listesini ekranda gösterir. Sonuç ayrıca JSON olarak kaydedilebilir.

Windows EXE, GitHub Actions workflow'u ile `PDF_KW_Selector_v0.1.0.exe` adıyla oluşturulur.

> v0.1.0 henüz PDF 2 karşılaştırmasını aktif etmez. Bu sürümün amacı PDF 1 motor keşfini gerçek PDF'lerle kullanıcı arayüzünden test etmektir.

---

## Ana hedef

Sisteme iki PDF verilir. Sistem kW değerlerini doğrudan tüm PDF'den toplamaz ve ilk bulduğu kW değerini karşılaştırmaz.

Doğrulama akışı kesin olarak üç ana aşamada çalışacaktır:

```text
PDF 1
  ↓
AŞAMA 1 — PDF 1'de doğru sayfayı bul
  ↓
PDF 1'de doğru ekipman / komponent / teknik alanı bul
  ↓
PDF 1 motor listesini oluştur
  ↓
AŞAMA 2 — PDF 2'de karşılık gelen ekipman / komponent / sayfaları bul
  ↓
PDF 2 motor listesini oluştur
  ↓
AŞAMA 3 — DATABASE ÜZERİNDEN KARŞILAŞTIR
  ↓
Eşleşiyor / Farklı / Bulunamadı / Belirsiz
```

Temel kural: **Önce PDF 1'i oku ve normalize et → sonra PDF 2'yi aynı yapıya dönüştür → en son iki normalize edilmiş motor listesini karşılaştır.**

---

# MOTOR SINIFLANDIRMA KURALI

PDF'deki hava yönü fan tipini belirler:

```text
Supply air  → Vantilatör → Vant
Return air  → Aspiratör  → Asp
```

Program aynı sayfada iki yön bulunuyorsa tüm sayfaya bakarak tahmin yapmaz; ilgili fan bloğunun lokal bağlamını çözmesi gerekir.

# MOTOR SAYISI KURALI — `1x1`, `2x1`, `3x1`

PDF'lerde motor grubu `NxM` biçiminde gösterilebilir.

İlk sayı fiziksel motor adedidir:

```text
1x1 → 1 motor
2x1 → 2 motor
3x1 → 3 motor
```

Örneğin:

```text
Supply air + 2x1
→ Vant 1
→ Vant 2
```

```text
Return air + 3x1
→ Asp 1
→ Asp 2
→ Asp 3
```

---

# DATABASE MİMARİSİ

Motorların karşılaştırılması ham PDF metninden yapılmayacaktır. PDF analizi sonucu normalize edilmiş lokal SQLite database kayıtları oluşturulacaktır.

```text
motors
────────────────────────────────────────────
equipment_id
equipment_type
component_type
component_index
component_label
power_kw
source_group
motor_count
source_page
confidence
```

Örnek:

```text
AHU1
Vant 1 | 3.0 kW | 2x1 | Page 6
Vant 2 | 3.0 kW | 2x1 | Page 6
Asp 1  | 2.2 kW | 3x1 | Page 7
Asp 2  | 2.2 kW | 3x1 | Page 7
Asp 3  | 2.2 kW | 3x1 | Page 7
```

Database lokal tutulur; normal kullanımda internet gerekmez.

---

# AŞAMA 1 — PDF 1

1. PDF'nin bütün sayfaları taranır.
2. Motor/fan teknik blokları puanlanır.
3. `Anma gücü [kW]` açık alanı aranır.
4. `Supply air` görülürse Vantilatör, `Return air` görülürse Aspiratör sınıflandırılır.
5. `1x1 / 2x1 / 3x1` fiziksel motor kayıtlarına genişletilir.
6. Her motor database'e ayrı kayıt olarak yazılır.

Mevcut örnek PDF'de hedef değer:

```text
Anma gücü [kW] 3,000 x (1x1)
→ 3.0 kW
→ Vant 1
```

Shaft Power, VSD dahil/hariç güç gibi başka kW alanları `Anma gücü` yerine kullanılmaz.

---

# AŞAMA 2 — PDF 2

PDF 1 database kayıtları hedef alınarak PDF 2'de aynı ekipman/komponent/motor indeksleri aranacaktır.

---

# AŞAMA 3 — KARŞILAŞTIRMA

İki normalize edilmiş database karşılaştırılır:

```text
AHU1 / Vant 1 / 3.0 kW ↔ AHU1 / Vant 1 / 3.0 kW ✓
AHU1 / Vant 2 / 3.0 kW ↔ AHU1 / Vant 2 / 4.0 kW ✗
AHU1 / Asp 1  / 2.2 kW ↔ AHU1 / Asp 1  / 2.2 kW ✓
```

Sonuç durumları:

```text
MATCH
MISMATCH
NOT_FOUND
AMBIGUOUS
REVIEW_REQUIRED
```

---

# GELİŞTİRME SIRASI

## Faz 1 — PDF 1 keşif ve motor database'i

- [x] kW değerlerini normalize et
- [x] `Anma gücü [kW]` alanını hedefle
- [x] doğru sayfayı puanla
- [x] `1x1 / 2x1 / 3x1` motor grubunu parse et
- [x] fiziksel motor kayıtlarına genişlet
- [x] lokal SQLite database modelini oluştur
- [x] Supply air → Vantilatör
- [x] Return air → Aspiratör temel kuralı
- [x] Windows masaüstü test arayüzü
- [x] Windows EXE build workflow
- [ ] gerçek PDF'den çoklu Vant/Asp komponentlerini otomatik keşfet
- [ ] PDF 1 database'ini gerçek parser çıktısıyla tamamen doldur

## Faz 2 — PDF 2 keşif

- [ ] PDF 1 database kayıtlarını hedef olarak kullan
- [ ] PDF 2'de aynı ekipmanları bul
- [ ] aynı komponentleri bul
- [ ] motor indekslerini eşleştir
- [ ] PDF 2 database'ini oluştur

## Faz 3 — Database karşılaştırma

- [ ] PDF1/PDF2 database'lerini karşılaştır
- [ ] MATCH / MISMATCH
- [ ] NOT_FOUND
- [ ] AMBIGUOUS
- [ ] REVIEW_REQUIRED
- [ ] tolerans sistemi
- [ ] kaynak sayfalarını raporla

## Faz 4 — Tam arayüz

```text
PDF 1 seç
PDF 2 seç
     ↓
AŞAMA 1 — PDF 1 Motor Listesi
     ↓
AŞAMA 2 — PDF 2 Motor Listesi
     ↓
AŞAMA 3 — Database Comparison
     ↓
Sonuç tablosu
```

## Faz 5 — Final Windows EXE

Final uygulama Windows'ta çift tıklayarak çalıştırılabilecek kurulum/EXE paketi olacaktır.

---

# SÜRÜMLEME KURALI

Her ana aşamanın sonunda test yapılıp ayrı bir sürüm oluşturulacaktır.

```text
v0.1.0 → PDF 1 masaüstü test
v0.2.0 → PDF 2 keşif
v0.3.0 → database karşılaştırma
v0.4.0 → çoklu motor/çoklu AHU
...
v1.0.0 → final
```
