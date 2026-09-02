# pdf_kw_selector

Engineering PDF'lerinden **doğru kW bilgisini bulup iki farklı PDF'deki karşılığını doğrulamak** için geliştirilen aşamalı doğrulama motoru.

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

# MOTOR SAYISI KURALI — `1x1`, `2x1`, `3x1`

PDF'lerde motor grubu `NxM` biçiminde gösterilebilir.

Bu projede ilk sayı fiziksel motor adedini ifade eder:

```text
1x1 → 1 motor
2x1 → 2 motor
3x1 → 3 motor
```

Örneğin PDF'de:

```text
Vantilatör   2x1
```

görülürse database'e:

```text
Vant 1
Vant 2
```

olarak iki ayrı motor kaydı yazılır.

PDF'de:

```text
Aspiratör   3x1
```

görülürse:

```text
Asp 1
Asp 2
Asp 3
```

olarak üç ayrı motor kaydı oluşturulur.

`x1` kısmı grubun kaynak gösterimini korur; fiziksel motor sayısını belirleyen sayı soldaki ilk sayıdır.

---

# DATABASE MİMARİSİ

Motorların karşılaştırılması ham PDF metninden yapılmayacaktır. PDF analizi sonucu önce **normalize edilmiş yerel SQLite database** oluşturulacaktır.

Database tablosu:

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
Equipment: AHU1

Vant 1 | 3.0 kW | 2x1 | Page 6
Vant 2 | 3.0 kW | 2x1 | Page 6
Asp 1  | 2.2 kW | 3x1 | Page 7
Asp 2  | 2.2 kW | 3x1 | Page 7
Asp 3  | 2.2 kW | 3x1 | Page 7
```

Bu database uygulamanın bilgisayarında lokal tutulacaktır. İnternet bağlantısı gerektirmeyecektir.

`local_database.py` SQLite bağlantısını, tablo oluşturmayı, motor listesini yazmayı ve okumayı sağlar. `motor_database.py` ise motor gruplarını fiziksel motor kayıtlarına genişletir.

---

# AŞAMA 1 — PDF 1'DE MOTORLARI BUL

Sistem önce PDF 1'i analiz eder.

## 1. Doğru sayfayı bul

Tüm sayfalar taranır ve hedef teknik bilgiye göre puanlanır.

Örneğin mevcut test PDF'inde sayfa 6 `Fan Data`, `Motor Data` ve `Anma gücü [kW] 3,000` bilgilerini aynı teknik blokta içerdiği için doğru adaydır. fileciteturn42file0L165-L180

## 2. Komponenti bul

PDF'de bulunan fan/aspiratör bilgisi komponent olarak çıkarılır.

Hedef isimler ilerleyen sürümlerde genişletilebilir:

```text
Vantilatör
Vant
Supply Fan
Fan
Plug Fan

Aspiratör
Asp
Exhaust Fan
Extract Fan
```

## 3. Motor grubunu bul

Komponentin yanında bulunan `1x1`, `2x1`, `3x1` vb. grup bilgisi bulunur.

## 4. Doğru kW alanını bul

Örneğin:

```text
Anma gücü [kW] 3,000 x (1x1)
```

hedef motor gücüdür.

Aynı sayfadaki:

```text
Shaft Power              2,090 kW
Tot. abs. güç VSD hariç  2,3998 kW
Tot. abs. VSD dahil güç  2,474 kW
```

ayrı teknik alanlar olduğu için motorun `Anma gücü` değeri yerine seçilmeyecektir. fileciteturn42file0L179-L187

## 5. Motor kayıtlarını oluştur

Örneğin:

```text
Vantilatör 2x1 + Anma gücü 3.0 kW
```

şu database kayıtlarına dönüşür:

```text
Vant 1 → 3.0 kW
Vant 2 → 3.0 kW
```

Aynı şekilde:

```text
Aspiratör 3x1 + Anma gücü 2.2 kW
```

şuna dönüşür:

```text
Asp 1 → 2.2 kW
Asp 2 → 2.2 kW
Asp 3 → 2.2 kW
```

---

# AŞAMA 2 — PDF 2'DE AYNI MOTORLARI BUL

PDF 1 database'e dönüştürüldükten sonra PDF 2 analiz edilir.

PDF 2'de de aynı yapı oluşturulur:

```text
Equipment
  ↓
Component
  ↓
Motor index
  ↓
Power type
  ↓
kW
  ↓
Database
```

Eşleştirme sırasında:

```text
AHU1 / Vant 1
AHU1 / Vant 2
AHU1 / Asp 1
AHU1 / Asp 2
AHU1 / Asp 3
```

gibi komponent indeksleri korunacaktır.

Bu sayede aynı AHU'da birden fazla motor olduğunda motorların sırası karışmayacaktır.

---

# AŞAMA 3 — KARŞILAŞTIRMA DATABASE ÜZERİNDEN

Karşılaştırma artık PDF'nin ham metnine bakarak yapılmayacak.

İki database kaydı karşılaştırılacaktır:

```text
PDF1 DATABASE                    PDF2 DATABASE

AHU1 / Vant 1 / 3.0 kW    ↔    AHU1 / Vant 1 / 3.0 kW
AHU1 / Vant 2 / 3.0 kW    ↔    AHU1 / Vant 2 / 4.0 kW
AHU1 / Asp 1  / 2.2 kW    ↔    AHU1 / Asp 1  / 2.2 kW
```

Sonuç:

```text
Vant 1    3.0 → 3.0 kW    ✓ MATCH
Vant 2    3.0 → 4.0 kW    ✗ MISMATCH
Asp 1     2.2 → 2.2 kW    ✓ MATCH
```

Bunun avantajı, PDF 2'de aynı sayfada bulunan `Unit Total Power` gibi başka kW değerlerinin karşılaştırma tablosuna yanlışlıkla girmemesidir. Test PDF'inde `Supply Fan Motor Power: 3 kW` ve `Unit Total Power: 4 kW` aynı dokümanda bulunduğu için bu ayrım zorunludur. fileciteturn13file3L174-L200

---

# EŞLEŞTİRME ANAHTARI

Her fiziksel motorun sabit bir karşılaştırma anahtarı olacaktır:

```text
Equipment ID
+ Component Type
+ Component Index
```

Örnek:

```text
AHU1 + vantilatör + 1 → Vant 1
AHU1 + vantilatör + 2 → Vant 2
AHU1 + aspiratör + 1 → Asp 1
AHU1 + aspiratör + 2 → Asp 2
AHU1 + aspiratör + 3 → Asp 3
```

İlerleyen aşamalarda model, hava debisi, motor modeli ve diğer teknik özellikler bu anahtara destekleyici eşleştirme sinyalleri olarak eklenecektir.

---

# BELİRSİZLİK KURALI

Sistem zorla motor eşleştirmeyecektir.

```text
MATCH
MISMATCH
NOT_FOUND
AMBIGUOUS
REVIEW_REQUIRED
```

Bir PDF'de `2x1` görülüyor fakat hangi kW'nin bu gruba ait olduğu güvenilir biçimde belirlenemiyorsa sonuç `REVIEW_REQUIRED` olacaktır.

Birden fazla motor adayı varsa sistem en yakın sayıyı seçip sessizce devam etmek yerine adayları ve güven skorlarını saklayacaktır.

---

# MEVCUT KOD DURUMU

- `stage1_page_discovery.py` → PDF 1'de doğru sayfa ve `Anma gücü [kW]` alanını bulur.
- `motor_database.py` → `1x1`, `2x1`, `3x1` gruplarını fiziksel motor kayıtlarına genişletir.
- `local_database.py` → normalize edilmiş motor listesini lokal SQLite database'e kaydeder.
- `tests/test_stage1.py` → gerçek PDF senaryosundaki 3.000 kW çıkarımını korur.
- `tests/test_motor_database.py` → Vant/Asp motor genişletmesini test eder.
- `tests/test_local_database.py` → database'e ayrı motor kayıtlarının yazılmasını test eder.

---

# GELİŞTİRME SIRASI

## Faz 1 — PDF 1 keşif ve motor database'i

- [x] kW değerlerini normalize et
- [x] ekipman ID normalizasyonu
- [x] aggregate/toplam güçleri ayır
- [x] `Anma gücü [kW]` alanını hedefle
- [x] doğru sayfayı puanla
- [x] `1x1 / 2x1 / 3x1` motor grubunu parse et
- [x] fiziksel motor kayıtlarına genişlet
- [x] lokal SQLite database modelini oluştur
- [x] Vant/Asp etiketleme temelini oluştur
- [ ] gerçek PDF'den çoklu Vant/Asp komponentlerini otomatik keşfet
- [ ] PDF 1 database'ini gerçek parser çıktısıyla doldur

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

## Faz 4 — Web arayüzü

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

## Faz 5 — Windows EXE

Final uygulama tek dosya/kurulum paketi şeklinde hazırlanacak ve Windows'ta **çift tıklayarak** çalıştırılabilecek.

---

# TEMEL MİMARİ KURALI

> **PDF'leri ham kW sayıları olarak değil, ekipman → komponent → fiziksel motor → teknik alan → kW kayıtları olarak database'e dönüştür. Daha sonra iki database'i karşılaştır.**

Bu mimari çok motorlu HVAC/AHU projelerinde motorların birbirine karışmasını önlemek ve ileride yüzlerce motoru güvenilir biçimde karşılaştırabilmek için kullanılacaktır.
