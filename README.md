# pdf_kw_selector

Engineering PDF'lerinden **doğru motor anma gücünü (kW) bulup fiziksel motor bazında normalize eden ve iki PDF arasında doğrulayan** motor.

## Güncel hedef

Sistem artık tekil PDF çifti mantığından **çoklu PDF + klasör tarama + proje eşleştirme + AHU eşleştirme + toplu motor karşılaştırma** mimarisine ilerliyor.

## Mevcut motor akışı

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

PDF 2 elektrik/sipariş çizimlerinde motor gücü öncelikle **özel motor bağlantı sayfasından** alınır.

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

## Kritik kural

Karşılaştırmanın hedefi **motor Rated Power / Anma gücü**dür.

Şunlar motor gücü olarak kullanılmaz:

- Unit Total Power
- Cooling Capacity
- Heating Capacity
- Shaft Power
- VSD dahil / hariç toplam güç
- Motorla ilgisiz diğer kW değerleri

# Multi-PDF / Project / AHU mimarisi

## Genel hedef akış

```text
PDF TOPLAMA
   ↓
PROJECT DISCOVERY
   ↓
PROJECT MATCHING
   ↓
AHU / EQUIPMENT DISCOVERY
   ↓
AHU MATCHING
   ↓
MOTOR DATABASE
   ↓
MOTOR kW COMPARISON
   ↓
TOPLU SONUÇ EKRANI
```

---

## Faz 1 — Multi-PDF Input ✅

Destekleniyor:

```text
[+] PDF Ekle
[+] Birden fazla PDF seç
[+] Klasör Ekle
[+] Alt klasörleri tara
```

Aynı dosya tekrar eklenmez; PDF olmayan girdiler atlanır.

### Veri modeli

```text
PdfInput
├── path
├── filename
├── source
└── size_bytes
```

---

## Faz 2 — Project Discovery ✅

PDF içindeki proje bilgisi dosya adından önce aranır.

Öncelik:

```text
1. Proje Name / Project Name
2. Project header
3. REVIEW
```

Raw değer, normalize değer, kaynak sayfa ve confidence korunur.

Örnek gerçek PDF:

```text
PDF 1:
Florya Uçuş Eğitim Binası Faz – 1-AHU

PDF 2:
Florya Uçus Egitim Binasi G
```

Bu iki ifade sonraki Project Matching aşamasında güvenli aday olarak değerlendirilir; sırf benziyor diye körlemesine birleştirilmez.

---

## Faz 3 — Project Matching ✅

`project_matching.py` ile:

```text
EXACT
HIGH_CONFIDENCE
MEDIUM_CONFIDENCE
REVIEW_REQUIRED
NO_MATCH
```

sonuçları üretiliyor.

One-to-one eşleştirme vardır. Sayısal kimlik çelişkileri gerektiğinde `REVIEW_REQUIRED` üretir.

---

## Faz 4 — AHU / Equipment Matching ✅

Yeni modül:

```text
ahu_matching.py
```

PDF içinden aşağıdaki kaynaklardan ekipman/AHU kimliği çıkarılır:

```text
Unit Reference
Unit Number
AHU token
```

Kimlikler normalize edilir:

```text
AHU_A_1   → AHU-A-1
AHU-A-01  → AHU-A-1
AHU_A_1A  → AHU-A-1A
AHU_A_2   → AHU-A-2
```

### Kritik güvenlik kuralı

```text
AHU-A-1
AHU-A-1A
AHU-A-2
```

birbirine sadece benzedikleri için otomatik eşleştirilmez.

Sonuç tipleri:

```text
EXACT
NORMALIZED_MATCH
REVIEW_REQUIRED
ONLY_IN_PDF1
ONLY_IN_PDF2
```

### Kullanılan gerçek test PDF'leri

Aynı proje altında farklı AHU'ları temsil eden üç gerçek PDF ile test senaryosu oluşturuldu:

```text
AHU_A_1(2).pdf → AHU-A-1
AHU_A_1A.pdf   → AHU-A-1A
AHU_A_2.pdf    → AHU-A-2
```

Bu üç ekipman **üç ayrı AHU** olarak korunmalıdır; `AHU-A-1A` hiçbir koşulda `AHU-A-1` ile sessizce birleştirilmemelidir.

---

## Faz 5 — Proje + AHU motor database

Proje ve AHU eşleşmesinden sonra mevcut motor parser'ları kullanılacak.

```text
Project
└── AHU / Equipment
    ├── PDF 1 motors
    └── PDF 2 motors
```

Karmaşık projelerde:

```text
2 Supply
2 Return
2 Activation / Reaktivasyon
```

ayrı fiziksel motor grupları olarak korunacak.

**Activation / Reaktivasyon Aspiratör'e dönüştürülmeyecek.**

---

## Faz 6 — Motor kW karşılaştırma

Ana anahtar:

```text
project
+ equipment
+ component_type
+ physical_motor_index
```

Sonuçlar:

```text
MATCH
MISMATCH
ONLY_IN_PDF1
ONLY_IN_PDF2
REVIEW_REQUIRED
```

---

## Faz 7 — Toplu karşılaştırma ekranı

Hedef ekran:

```text
PROJE → AHU → MOTOR → PDF1 kW ↔ PDF2 kW
```

Filtreler:

- Proje
- AHU
- Motor tipi
- MATCH
- MISMATCH
- ONLY PDF1
- ONLY PDF2
- REVIEW

---

## Faz 8 — Rapor

Planlanan çıktılar:

```text
JSON
CSV
Excel
```

Rapor seviyeleri:

```text
1. Genel proje özeti
2. Proje → AHU özeti
3. AHU → motor özeti
4. Sadece hatalı motorlar
5. Sadece eşleşmeyen PDF/AHU'lar
6. REVIEW listesi
```

---

# Teknik mimari

```text
INPUT
├── batch_input.py

PROJECT
├── project_discovery.py
└── project_matching.py

EQUIPMENT
└── ahu_matching.py

MOTOR
├── stage1_page_discovery.py
├── stage2_pdf_discovery.py
├── motor_database.py
└── motor_compare.py

UI
└── desktop_app.py
```

Yeni katmanlar mevcut motor parser'larının üzerine kurulur.

---

# Geliştirme sırası

## Milestone 1 — Multi-PDF Input ✅

```text
[x] Çoklu PDF seçimi
[x] Klasör seçimi
[x] Alt klasör tarama
[x] Duplicate kontrolü
[x] PDF input modeli
[x] GUI entegrasyonu
[x] Testler
```

## Milestone 2 — Project Discovery ✅

```text
[x] Project Name extractor
[x] Raw / normalized değerler
[x] Source page / field
[x] Confidence
[x] GUI entegrasyonu
[x] Testler
```

## Milestone 3 — Project Matching ✅

```text
[x] Exact match
[x] Normalized match
[x] Candidate scoring
[x] Ambiguous detection
[x] REVIEW_REQUIRED
[x] One-to-one pairing
[x] Testler
```

## Milestone 4 — AHU Matching ✅

```text
[x] PDF içinden equipment listesi
[x] AHU normalize
[x] PDF1 ↔ PDF2 AHU matching engine
[x] ONLY_IN_PDF1
[x] ONLY_IN_PDF2
[x] REVIEW_REQUIRED
[x] 1 / 1A / 2 ayrımı
[x] Testler
```

## Milestone 5 — Proje + AHU bazlı toplu analiz ⏳

```text
[ ] Project → AHU hierarchical grouping
[ ] Eşleşen project altında AHU pairing
[ ] AHU → motor database bağlantısı
[ ] batch analyzer
[ ] toplu sonuç modeli
```

## Milestone 6 — Toplu karşılaştırma ekranı ⏳

```text
[ ] Proje listesi
[ ] AHU listesi
[ ] Motor detayları
[ ] Filtreler
[ ] REVIEW ekranı
[ ] Kaynak PDF/sayfa bağlantıları
```

## Milestone 7 — Rapor + EXE ⏳

```text
[ ] JSON
[ ] CSV
[ ] Excel
[ ] Windows EXE
[ ] örnek büyük proje testi
```
