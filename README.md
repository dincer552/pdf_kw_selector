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
PDF 1'de doğru ekipman / motor / teknik alanı bul
  ↓
PDF 1 kW değerini çıkar
  ↓
AŞAMA 2 — PDF 2'de doğru sayfayı bul
  ↓
PDF 2'de PDF 1'de bulunan ekipmanın karşılığını bul
  ↓
PDF 2 kW değerini çıkar
  ↓
AŞAMA 3 — KARŞILAŞTIR
  ↓
Eşleşiyor / Farklı / Bulunamadı / Belirsiz
```

Bu sıra projenin temel mimari kuralıdır: **önce PDF 1, sonra PDF 2, en son karşılaştırma.**

---

## Neden sadece `kW` aramak yeterli değil?

Gerçek mühendislik PDF'lerinde aynı dokümanda birçok farklı kW bulunabilir. Test PDF'inde aynı AHU için fan motor gücü **3 kW**, cooling capacity **44,63 kW**, VSD dahil güç yaklaşık **2,474 kW**, VSD hariç güç yaklaşık **2,3998 kW** ve shaft power **2,090 kW** olarak ayrı teknik alanlarda yer alıyor. fileciteturn13file0L17-L34 fileciteturn13file2L115-L145

Diğer PDF'de ise `Supply Fan Motor Power: 3 kW` ile `Unit Total Power: 4 kW` aynı dokümanda bulunuyor. Bu nedenle `4 kW` fan motor gücü olarak seçilmemelidir. fileciteturn13file3L174-L200

Sonuç olarak sistem yalnızca sayı aramayacak; **kW değerinin hangi ekipmana, hangi komponent'e ve hangi teknik alana ait olduğunu belirleyecek.**

---

# AŞAMA 1 — PDF 1'de doğru kW bilgisini bul

İlk motorumuz **PDF 1** olacaktır.

### 1.1 Doküman kimliğini çıkar

Önce PDF 1'den:

- Proje adı
- Birim / ekipman numarası
- Ekipman tipi
- Model
- Fan modeli
- Fan adedi
- Hava debisi
- Teknik alan başlıkları

çıkarılır.

Test PDF'inde `AHU-1`, `FLNG 30x30`, `RH35C.1R/SM12-B28`, `6.000 m³/h` gibi bilgiler ilk sayfada bulunuyor. fileciteturn13file0L10-L26

### 1.2 Doğru sayfayı bul

Sistem `kW` kelimesini bulduğu ilk sayfayı seçmeyecek.

Her sayfa hedef teknik bilgi açısından puanlanacak:

```text
Sayfa 1 → Genel AHU bilgileri
Sayfa 2 → Ecodesign
Sayfa 3 → Geometrik çizim
...
Sayfa 6 → Fan Data / Motor Data       ← yüksek aday
```

Test PDF'inde sayfa 6'da `Fan Data`, `Motor Data` ve `Anma gücü [kW] 3,000` aynı teknik blok içinde bulunuyor. fileciteturn13file2L115-L133

### 1.3 Doğru teknik alanı bul

Bulunan kW adayları anlamlarına göre sınıflandırılacak:

```text
fan_motor_power
motor_power
unit_total_power
cooling_capacity
heating_capacity
shaft_power
vfd_power
other
```

Hedef `fan_motor_power` ise `cooling_capacity`, `unit_total_power`, `shaft_power` vb. değerler fan motor gücü adayı olmayacak.

### 1.4 PDF 1 sonucu

Her bulunan motor ayrı kayıt olarak tutulacak:

```text
Document: PDF-1
Equipment: AHU-1
Normalized Equipment: AHU1
Role: Supply Fan
Motor: RH35C.1R/SM12-B28
Quantity: 1x1
Power Type: fan_motor_power
Power: 3.000 kW
Page: 6
Confidence: high
```

**Sayfa numarası, teknik alan ve çevresindeki metin mutlaka saklanacaktır.** Böylece sonuç daha sonra denetlenebilir olacaktır.

---

# AŞAMA 2 — PDF 2'de aynı motorun kW bilgisini bul

PDF 1'de hedef motor belirlendikten sonra sistem PDF 2'ye geçer.

Burada amaç PDF 2'de herhangi bir kW bulmak değil, **PDF 1'de bulunan aynı ekipman/komponent'in karşılığını bulmaktır.**

### 2.1 Ekipman eşleştirme

Öncelik sırasıyla:

1. Ekipman ID
2. Normalize edilmiş ekipman ID
3. Komponent rolü (`supply_fan`, `return_fan` vb.)
4. Fan/motor modeli
5. Model numarası
6. Hava debisi
7. Motor adedi
8. Teknik açıklama

kullanılacaktır.

Örneğin:

```text
AHU-1
AHU_01
AHU 001
```

aynı ekipman olarak:

```text
AHU1
```

şeklinde normalize edilir.

Mevcut kodda ekipman ID normalizasyonu temel olarak zaten bulunmaktadır. fileciteturn6file0L1-L2

### 2.2 PDF 2 doğru sayfasını bul

Eşleşen ekipman bulunduğunda PDF 2'de bu ekipmana ait sayfalar puanlanır.

Örneğin test PDF'inin ilk sayfasında `AHU_01`, `6.000 m³/h`, `3 kW (1x1)`, `4 kW`, `Supply Fan Motor Power` ve `Unit Total Power` birlikte bulunuyor. fileciteturn13file3L157-L200

Bu yüzden sistem sadece `3` ve `4` sayılarını görmeyecek; **hangi teknik alanın hangi değere ait olduğunu** belirleyecek.

### 2.3 Aynı teknik alanı seç

PDF 1 hedefi:

```text
AHU1 / Supply Fan / fan_motor_power
```

ise PDF 2'de de aynı kombinasyon aranacak:

```text
AHU1 / Supply Fan / fan_motor_power
```

`Unit Total Power` gibi başka bir alan aynı ekipmana ait olsa bile fan motor gücüyle eşleştirilmeyecek.

### 2.4 PDF 2 sonucu

```text
Document: PDF-2
Equipment: AHU_01
Normalized Equipment: AHU1
Role: Supply Fan
Power Type: fan_motor_power
Power: 3.000 kW
Page: 1
Confidence: high
```

---

# AŞAMA 3 — İKİ BULUNAN VERİYİ KARŞILAŞTIR

Karşılaştırma motoru ancak ilk iki aşama tamamlandıktan sonra çalışacaktır.

Örnek:

```text
PDF 1
AHU1 / Supply Fan / fan_motor_power / 3.000 kW

PDF 2
AHU1 / Supply Fan / fan_motor_power / 3.000 kW
```

Sonuç:

```text
AHU1
Supply Fan Motor Power

PDF 1: 3.000 kW — Page 6
PDF 2: 3.000 kW — Page 1

STATUS: MATCH
```

---

# ÇOKLU MOTOR / ÇOKLU EKİPMAN

Bu proje tek motorlu örnek için yapılmıyor. Gelecekte bir PDF içinde onlarca AHU ve her AHU içinde birden fazla motor olabilir.

Örnek:

```text
AHU-01 → Supply Fan → 3 kW
AHU-01 → Return Fan  → 2.2 kW
AHU-02 → Supply Fan → 5.5 kW
AHU-02 → Return Fan  → 4 kW
AHU-03 → Supply Fan → 7.5 kW
```

Sistem bunları tek bir `kW listesi` olarak tutmayacak.

Her motor ayrı bir komponent kaydı olacaktır:

```text
AHU1
 ├── Supply Fan
 │    └── Motor → 3.0 kW
 └── Return Fan
      └── Motor → 2.2 kW

AHU2
 ├── Supply Fan
 │    └── Motor → 5.5 kW
 └── Return Fan
      └── Motor → 4.0 kW
```

PDF 2 de aynı yapıya dönüştürülecek ve motorlar tek tek eşleştirilecektir:

```text
PDF1 AHU1 / Supply Fan → PDF2 AHU1 / Supply Fan
PDF1 AHU1 / Return Fan → PDF2 AHU1 / Return Fan
PDF1 AHU2 / Supply Fan → PDF2 AHU2 / Supply Fan
PDF1 AHU2 / Return Fan → PDF2 AHU2 / Return Fan
```

Böylece aynı AHU içindeki Supply Fan ile Return Fan birbirine karıştırılmayacaktır.

---

# MOTOR EŞLEŞTİRME SKORU

Bir motorun PDF 2'deki karşılığını bulurken birden fazla özellik birlikte değerlendirilecek:

```text
Ekipman ID                    → çok güçlü
Komponent rolü                → çok güçlü
Fan/motor modeli              → çok güçlü
Teknik alan                   → çok güçlü
Motor adedi                   → güçlü
Hava debisi                   → güçlü
Model numarası                → orta/güçlü
Sayfa/tablo bağlamı           → destekleyici
Metin yakınlığı               → son destek
```

Örneğin:

```text
AHU1 + Supply Fan + Motor Power
```

ile:

```text
AHU1 + Return Fan + Motor Power
```

aynı AHU'ya ait olsa bile aynı komponent kabul edilmeyecektir.

Birden fazla aday yakın skor alırsa sistem zorla seçim yapmayacak ve sonucu `AMBIGUOUS` olarak işaretleyecektir.

---

# SAYFA BULMA MOTORU

Sayfa keşfi ayrı bir katman olacaktır:

```text
PDF
 ↓
Page Scanner
 ↓
Page Feature Extraction
 ↓
Target Page Scoring
 ↓
Relevant Pages
```

`fan_motor_power` için örnek sinyaller:

```text
"Motor Data"             + yüksek
"Fan Data"               + yüksek
"Motor Power"             + yüksek
"Supply Fan"              + yüksek
"Anma gücü"               + yüksek
"kW"                      + düşük/orta
"Cooling Capacity"        - yüksek
"Heating Capacity"        - yüksek
"Unit Total Power"        - yüksek
```

Böylece **sayfa seçimi**, **teknik alan seçimi** ve **değer seçimi** birbirinden ayrılmış olacaktır.

---

# VERİ MODELİ

İleride her motor yaklaşık olarak şu yapıda tutulacaktır:

```json
{
  "equipment_id": "AHU1",
  "equipment_type": "AHU",
  "component_role": "supply_fan",
  "component_id": "AHU1-SF1",
  "fan_model": "RH35C.1R/SM12-B28",
  "motor_power_kw": 3.0,
  "quantity": 1,
  "source": {
    "document": "PDF-1",
    "page": 6,
    "field": "fan_motor_power"
  },
  "confidence": 0.96
}
```

Bu veri modeli karşılaştırma motorundan bağımsız tutulacaktır.

---

# HATA DURUMLARI

Sistem hiçbir durumda zorla eşleştirme yapmamalıdır.

### MATCH

```text
PDF1: 3.0 kW
PDF2: 3.0 kW
→ MATCH
```

### MISMATCH

```text
PDF1: 3.0 kW
PDF2: 4.0 kW
→ MISMATCH
```

### NOT_FOUND

```text
PDF1: AHU2 / Supply Fan / 5.5 kW
PDF2: karşılık bulunamadı
→ NOT_FOUND
```

### AMBIGUOUS

```text
PDF2'de aynı motor için birden fazla güçlü aday
→ AMBIGUOUS
```

### REVIEW_REQUIRED

```text
kW bulundu fakat teknik anlamı güvenilir biçimde belirlenemedi
→ REVIEW_REQUIRED
```

---

# GELİŞTİRME SIRASI

## Faz 1 — Temel çıkarma

- [x] kW değerlerini normalize et
- [x] ekipman ID normalizasyonu
- [x] aggregate/toplam güçleri ayır
- [x] temel fan motoru aday seçimi
- [x] `W → kW` dönüşümü

## Faz 2 — PDF 1 keşif motoru

- [ ] PDF'yi sayfa bazında parse et
- [ ] Her sayfaya hedef alan skorları ver
- [ ] Hedef ekipmanı bul
- [ ] İlgili fan/motor sayfasını seç
- [ ] Doğru `power_type` alanını seç
- [ ] Sayfa + alan + bağlamı kaydet

## Faz 3 — PDF 2 keşif motoru

- [ ] PDF 1 sonucundaki ekipmanı PDF 2'de ara
- [ ] Ekipman ID normalize et
- [ ] Komponent rolünü eşleştir
- [ ] Fan/motor modelini eşleştir
- [ ] İlgili PDF 2 sayfasını seç
- [ ] Aynı `power_type` alanını bul

## Faz 4 — Çoklu motor eşleştirme

- [ ] PDF 1'de bütün motor komponentlerini çıkar
- [ ] PDF 2'de bütün motor komponentlerini çıkar
- [ ] Component ID üret
- [ ] Motorları birebir eşleştir
- [ ] Duplicate/ambiguous durumlarını yakala
- [ ] Eşleşme güven skoru üret

## Faz 5 — Karşılaştırma

- [ ] Aynı komponenti doğrula
- [ ] kW değerlerini karşılaştır
- [ ] Tolerans sistemi ekle
- [ ] MATCH / MISMATCH
- [ ] NOT_FOUND
- [ ] AMBIGUOUS
- [ ] REVIEW_REQUIRED

## Faz 6 — Web arayüzü

```text
┌─────────────────────────────────────────────┐
│ PDF KW VERIFICATION                         │
│                                             │
│ PDF 1: [ Dosya seç ]                        │
│ PDF 2: [ Dosya seç ]                        │
│                                             │
│              [ ANALİZ ET ]                  │
└─────────────────────────────────────────────┘

                 ↓

AŞAMA 1   PDF 1 doğru sayfa/kW aranıyor... ✓
AŞAMA 2   PDF 2 karşılık/kW aranıyor...    ✓
AŞAMA 3   Eşleşmeler karşılaştırılıyor...  ✓

                 ↓

AHU1 / Supply Fan
PDF 1       3.0 kW   Page 6
PDF 2       3.0 kW   Page 1
SONUÇ       ✓ MATCH
```

Kullanıcı sonuçta **PDF adı + sayfa + ekipman + komponent + teknik alan + bulunan kW + eşleşme skoru** bilgilerini görebilmelidir.

---

# Mevcut kod

Mevcut kodda temel kW aday seçimi, bağlam puanlama, ekipman ID normalizasyonu ve aggregate alanları cezalandırma mantığı bulunuyor. fileciteturn6file0L1-L2

Yeni mimaride bu katman korunacak fakat üstüne ayrı olarak:

```text
Page Discovery
      ↓
Equipment Discovery
      ↓
Component Discovery
      ↓
Technical Field Classification
      ↓
KW Extraction
      ↓
PDF-1 ↔ PDF-2 Component Matching
      ↓
KW Validation
```

katmanları kurulacaktır.

## Temel mimari kural

> **Önce PDF 1'de doğru ekipmanı ve doğru sayfayı bul → PDF 1'de doğru teknik kW alanını bul → PDF 2'de aynı ekipman/komponenti bul → PDF 2'de aynı teknik kW alanını bul → en son iki değeri karşılaştır.**

Sistem hiçbir zaman:

> `PDF'deki bütün kW'ları çıkar → sayıları sırayla karşılaştır`

mantığıyla çalışmayacaktır.

Bu ayrım, özellikle çoklu motor bulunan büyük HVAC/AHU projelerinde güvenilirliğin temelidir.
