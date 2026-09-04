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

## Faz 5 — Batch Motor Analysis 🚧 AKTİF

Yeni orchestrator:

```text
batch_analysis.py
```

Artık motor analizi doğrudan tüm PDF'ler üzerinde yapılmak yerine hiyerarşi ile yürütülüyor:

```text
PROJECT
└── AHU
    ├── PDF 1 motorları
    └── PDF 2 motorları
```

Akış:

```text
1. PDF'leri keşfet
2. Project Discovery
3. Projeleri grupla
4. Project Matching ile birebir eşleştir
5. Eşleşen proje içindeki AHU'ları çıkar
6. AHU Matching ile birebir eşleştir
7. Sadece eşleşen AHU'nun motorlarını analiz et
8. Fiziksel motor kayıtlarına genişlet
9. Motor index bazında kW karşılaştır
```

Ana motor anahtarı:

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
```

### PDF 2 için önemli geliştirme

Dedicated `Supply / Return / Exhaust / Activation Motor Connections` sayfası varsa o sayfa önceliklidir.

Bağlantı sayfası yoksa kontrollü bir **Fan Motor Power summary fallback** kullanılır.

Örneğin yalnız Supply motoru bulunan özet:

```text
Fan Motor Power / Nominal Rpm
11 [kW] (2x1)
```

→ `Vant 1 = 11 kW`
→ `Vant 2 = 11 kW`

Bu fallback, PDF2'nin sadece supply fan özeti bulunan gerçek formatlarını da destekler.

### Karmaşık fan grupları

Özellikle:

```text
2 Supply
2 Return
2 Activation / Reaktivasyon
```

gibi projelerde aileler kesinlikle birbirine karıştırılmaz.

**Activation / Reaktivasyon Aspiratör değildir; ayrı komponent ailesidir.**

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

Ayrıca gerçek `AHU-A-1` örneğinde PDF 1 seçim tarafında 2 adet 11 kW Supply motoru bulunuyor; üretim tarafında da `Supply` için `2x1` ve 11 kW bilgisi mevcut. Bu yapı Batch Motor Analysis için temel smoke-test senaryosudur.

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
[x] Testler
```

## Milestone 5 — Batch Motor Analysis 🚧

```text
[x] Project → AHU hierarchical grouping
[x] Eşleşen project altında AHU pairing
[x] AHU → motor database bağlantısı
[x] Batch analysis orchestrator
[x] PDF2 single-supply summary fallback
[ ] Çoklu gerçek proje smoke testleri
[ ] Motor sonuçlarına Project/AHU metadata eklenmesi
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
