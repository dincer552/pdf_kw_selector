# pdf_kw_selector

Engineering PDF'lerinden **doğru motor anma gücünü (kW) bulup fiziksel motor bazında normalize eden ve iki PDF arasında doğrulayan** motor.

## Güncel durum

Sistem artık tekil PDF çifti mantığından **çoklu PDF + klasör tarama + proje keşfi/eşleştirme + AHU keşfi/eşleştirme + proje/AHU bazlı toplu motor analizi** mimarisine geçti.

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
BATCH MOTOR ANALYSIS
   ↓
PDF1 motor database ↔ PDF2 motor database
   ↓
MATCH / MISMATCH / ONLY_IN_PDF1 / ONLY_IN_PDF2
```

## Motor mantığı

```text
Supply air  → Vantilatör → Vant
Return air  → Aspiratör  → Asp
Exhaust air → Aspiratör  → Asp
Activation  → Reaktivasyon → ayrı aile

1x1 → 1 fiziksel motor
2x1 → 2 fiziksel motor
3x1 → 3 fiziksel motor
```

Karşılaştırma hedefi **motor Rated Power / Anma gücü**dür. `Unit Total Power`, kapasite, shaft power veya VSD toplam gücü motor Rated Power yerine kullanılmaz.

---

# Fazlar

## Faz 1 — Multi-PDF Input ✅

```text
[+] PDF Ekle
[+] Birden fazla PDF seç
[+] Klasör Ekle
[+] Alt klasörleri tara
```

Aynı dosya tekrar eklenmez ve PDF olmayan girdiler atlanır.

## Faz 2 — Project Discovery ✅

PDF içindeki gerçek proje adı dosya adından önce aranır.

Öncelik:

```text
1. Proje Name / Project Name
2. Project header
3. REVIEW
```

Raw değer, normalize değer, kaynak sayfa/alan ve confidence korunur.

Gerçek test örneği:

```text
PDF 1:
Florya Uçuş Eğitim Binası Faz – 1-AHU

PDF 2:
Florya Uçus Egitim Binasi G
```

Türkçe karakter, aksan ve tire farklılıkları normalize edilir; kaynak metin kaybolmaz.

Project Discovery ayrıca Systemair mixed-header satırlarında `Creation date`, `Revision Date` gibi kolonları proje adına dahil etmez; boş `Proje Name:` alanında `Order Number`, numarası ve `Unit Number` gibi doküman alanlarını atlayıp sonraki doğal dil proje satırını arar.

## Faz 3 — Project Matching ✅

`project_matching.py` ile:

```text
EXACT
HIGH_CONFIDENCE
MEDIUM_CONFIDENCE
REVIEW_REQUIRED
NO_MATCH
```

One-to-one proje eşleştirme uygulanır. Çelişkili sayısal kimliklerde otomatik eşleşme yerine `REVIEW_REQUIRED` tercih edilir.

## Faz 4 — AHU / Equipment Matching ✅

`ahu_matching.py` PDF içinden:

```text
Unit Reference
Unit Number
AHU token
```

kaynaklarını kullanır.

Örnek normalize:

```text
AHU_A_1   → AHU-A-1
AHU-A-01  → AHU-A-1
AHU_A_1A  → AHU-A-1A
AHU_A_2   → AHU-A-2
```

Kritik kural:

```text
AHU-A-1
AHU-A-1A
AHU-A-2
```

birbirine benzedikleri için otomatik eşleştirilmez.

Gerçek test grupları:

```text
A serisi: AHU-A-1 / AHU-A-1A / AHU-A-2
C serisi: AHU-C-1 / AHU-C-1-A / AHU-C-2-A
```

Bu testlerde farklı AHU kimlikleri birbirine yanlış bağlanmadan ayrıştırılmıştır.

## Faz 5 — Batch Motor Analysis 🚧 AKTİF

`batch_analysis.py` artık **Project → AHU → fiziksel motor** zincirini tek bir orchestration katmanında yürütüyor.

```text
PDF 1 / PDF 2
      ↓
Project Discovery
      ↓
Project Matching
      ↓
AHU Discovery
      ↓
AHU Matching
      ↓
Eşleşen AHU dosyalarını seç
      ↓
Stage 1 / Stage 2 motor keşfi
      ↓
Fiziksel motor expansion
      ↓
Motor index bazında kW karşılaştırması
```

### Batch kuralları

- Aynı fiziksel motor birden fazla örtüşen PDF'de görünüyorsa tek kayda indirgenir.
- PDF2 tarafında aynı fan ailesinin birden fazla Motor Connections sayfası varsa motor index'leri dosyalar arasında devam ettirilir.
- `1x1 / 2x1 / 3x1` fiziksel motor sayısı olarak korunur.
- `Activation / Reaktivasyon` ayrı aile olarak korunur.
- Eşleşmeyen veya belirsiz AHU'ya motor karşılaştırması uygulanmaz.

### PDF2 motor keşfi

Öncelik sırası:

```text
1. Supply / Return / Exhaust / Activation Motor Connections
2. Motor Connections üzerindeki 3 faz kW
3. Dedicated bağlantı sayfası yoksa kontrollü Fan Motor Power summary fallback
```

Örneğin:

```text
Fan Motor Power / Nominal Rpm
11 [kW] (2x1)
```

summary-only fallback ile:

```text
Vant 1 = 11 kW
Vant 2 = 11 kW
```

olarak fiziksel motorlara genişletilir.

### Güncel gerçek smoke-test

Kullanılan örnek:

```text
PDF 1: AHU_A_1(3).pdf
PDF 2: EC-Florya-Rev5-Üreti_AHU-A-1_PER_18(2).pdf
```

Beklenen yapı:

```text
Proje:
Florya Uçuş Eğitim Binası Faz – 1-AHU
↕
Florya Uçus Egitim Binasi G

AHU:
AHU-A-1
↕
AHU-A-1

Motor:
Vant 1   11.0 ↔ 11.0  MATCH
Vant 2   11.0 ↔ 11.0  MATCH
```

PDF1 seçim dokümanında Supply fan motor gücü `11 kW (2x1)` olarak bulunuyor. PDF2 üretim dokümanında aynı AHU için `Fan Motor Power / Nominal Rpm 11 kW (2x1)` bulunuyor.

### Karmaşık fan grupları

Özellikle:

```text
2 Supply
2 Return
2 Activation / Reaktivasyon
```

gibi projelerde aileler kesinlikle birbirine karıştırılmaz.

**Activation / Reaktivasyon Aspiratör değildir; ayrı komponent ailesidir.**

Önceki gerçek testte iki ayrı `Return Motor Connections` sayfasının `Asp 1` ve `Asp 2` olarak ayrılması da doğrulanmıştır.

---

# Şu an kullanılan gerçek test PDF'leri

Testlerde farklı AHU ve motor yapıları kullanılıyor:

```text
AHU_A_1(2).pdf   → AHU-A-1
AHU_A_1A.pdf     → AHU-A-1A
AHU_A_2.pdf      → AHU-A-2

AHU_C_1.pdf      → AHU-C-1
AHU_C_1_A.pdf    → AHU-C-1-A
AHU_C_2_A.pdf    → AHU-C-2-A
```

Batch smoke-test:

```text
AHU_A_1(3).pdf
EC-Florya-Rev5-Üreti_AHU-A-1_PER_18(2).pdf
```

Bu çift aynı proje + aynı AHU + aynı 2 adet Supply motoru senaryosunu doğrulamak için kullanılıyor.

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

BATCH
└── batch_analysis.py

MOTOR
├── stage1_page_discovery.py
├── stage2_pdf_discovery.py
├── motor_database.py
└── motor_compare.py

UI
└── desktop_app.py
```

Yeni batch katmanı mevcut motor parser'larını yeniden yazmak yerine onların üstünde orchestration yapar.

---

# Milestone durumu

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
[x] Systemair mixed-header metadata temizleme
[x] Çok satırlı Proje Name alanı
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
[x] PDF1 ↔ PDF2 AHU matching
[x] ONLY_IN_PDF1
[x] ONLY_IN_PDF2
[x] REVIEW_REQUIRED
[x] 1 / 1A / 2 ayrımı
[x] A serisi gerçek test
[x] C serisi gerçek test
[x] Testler
```

## Milestone 5 — Batch Motor Analysis 🚧

```text
[x] Project → AHU hierarchical grouping
[x] Eşleşen project altında AHU pairing
[x] AHU → motor database bağlantısı
[x] Batch analysis orchestrator
[x] PDF2 single-supply summary fallback
[x] Örtüşen fiziksel motor deduplication
[x] Çoklu PDF2 motor index devamlılığı
[x] GUI entegrasyonu
[x] 2x1 Supply smoke-test
[ ] Çoklu gerçek proje smoke testleri
[ ] Motor sonuçlarına Project/AHU metadata'nın result modeline taşınması
[ ] REVIEW_REQUIRED'ın motor katmanına tam taşınması
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
[ ] Büyük proje testi
```
