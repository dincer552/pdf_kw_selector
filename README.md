# pdf_kw_selector

Engineering PDF'lerinden **doğru motor anma gücünü (kW) bulup fiziksel motor bazında normalize eden ve iki PDF arasında doğrulayan** motor.

## Güncel durum — v0.3.3

Mevcut sistem tekil PDF çiftlerinde PDF 1 (seçim/referans) ile PDF 2 (elektrik/sipariş) arasında motor bazında kW karşılaştırması yapabiliyor.

Bir sonraki ana hedef artık tek bir PDF çifti değil, **çoklu PDF + klasör tarama + proje eşleştirme + AHU eşleştirme + toplu karşılaştırma** sistemine geçmektir.

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

# 🚀 Yeni ana geliştirme planı — Multi-PDF Project Manager

Hedefimiz programı tek PDF çifti analiz eden bir araçtan, **klasörlerden yüzlerce PDF'i alıp projeleri otomatik eşleştiren ve sonunda toplu motor kW karşılaştırması çıkaran bir mühendislik kontrol aracına** dönüştürmek.

## Genel hedef akış

```text
KULLANICI
   │
   ├── Birden fazla PDF seç
   │       veya
   └── Bir / birden fazla klasör seç
   │
   ▼
[1] PDF TOPLAMA / TARAMA
   │
   ▼
[2] PDF METADATA + PROJE İSMİ ÇIKARMA
   │
   ▼
[3] PDF'LERİ PROJE BAZINDA GRUPLAMA
   │
   ▼
[4] PROJE İSİMLERİNİ EŞLEŞTİRME
   │
   ▼
[5] EŞLEŞEN PROJE İÇİN AHU / EQUIPMENT EŞLEŞTİRME
   │
   ▼
[6] PDF 1 MOTOR DATABASE + PDF 2 MOTOR DATABASE
   │
   ▼
[7] MOTOR BAZINDA kW KARŞILAŞTIRMA
   │
   ▼
[8] TOPLU KARŞILAŞTIRMA EKRANI
   │
   ├── Proje özeti
   ├── AHU özeti
   ├── Motor özeti
   ├── MATCH
   ├── MISMATCH
   ├── ONLY PDF1
   ├── ONLY PDF2
   └── REVIEW / AMBIGUOUS
```

---

## Faz 1 — Çoklu PDF ekleme

### Amaç

Kullanıcı artık tek tek PDF seçmek zorunda kalmayacak.

Desteklenecek girişler:

```text
[+] PDF Ekle
[+] Birden fazla PDF seç
[+] Klasör Ekle
[+] Alt klasörleri tara
```

Program bütün `.pdf` dosyalarını tek bir çalışma havuzuna alacak.

### Gereksinimler

- Aynı PDF'nin iki kez eklenmesini engelle.
- Dosya adı, tam yol, dosya boyutu ve mümkünse hash bilgisini tut.
- Klasör taramasında alt klasörleri opsiyonel olarak dahil et.
- Bozuk / okunamayan PDF'yi tüm işlemi durdurmadan `ERROR` olarak işaretle.
- Kullanıcıya toplam PDF sayısını göster.

Örnek:

```text
3 klasör
   ↓
147 PDF bulundu
   ↓
142 okunabilir
5 hata
```

### Yeni veri modeli

```text
PDFDocument
├── path
├── filename
├── file_hash
├── page_count
├── project_name
├── project_name_raw
├── document_type
├── equipment_ids[]
└── status
```

---

## Faz 2 — PDF'lerden proje ismini çıkarma

### Amaç

Dosya adına güvenmek yerine PDF'nin içindeki gerçek proje bilgisini bulacağız.

Öncelik sırası:

```text
1. PDF içindeki açık Proje Name / Project Name alanı
2. Title Page / kapak bilgisi
3. Unit / Project metadata
4. Dosya adı
5. Gerekirse REVIEW
```

### Önemli kural

PDF'de aynı anda çok sayıda isim, müşteri, proje, sipariş veya ekipman bilgisi bulunabilir. Sistem rastgele ilk metni proje adı olarak kabul etmeyecek.

Her proje adı için:

```text
raw value
normalized value
source page
source field
confidence
```

tutulacak.

Örnek:

```text
Raw:
25END092

Normalized:
25END092

Source:
Title Page / Project Name

Confidence:
HIGH
```

---

## Faz 3 — PDF'leri proje bazında gruplama

Proje adı çıkarıldıktan sonra PDF'ler proje altında toplanacak.

```text
PROJE A
├── seçim PDF 1
├── elektrik PDF 2
├── elektrik PDF 3
└── diğer çizimler

PROJE B
├── seçim PDF 1
└── elektrik PDF 2
```

Aynı projenin farklı PDF'lerinde küçük yazım farkları olabileceği için doğrudan string eşitliği yeterli olmayacak.

Örneğin:

```text
25END092
25END-092
25END_092
25END 092
```

normalize edilerek aynı aday proje olarak değerlendirilecek.

Ancak **fazla agresif normalizasyon yapılmayacak**; yanlış iki projeyi birleştirmek yerine `REVIEW` üretmek tercih edilecek.

---

## Faz 4 — Proje isimlerini eşleştirme motoru

Burada iki seviyeli eşleştirme yapılacak.

### Seviye A — Kesin eşleşme

```text
normalize(project_name_a) == normalize(project_name_b)
```

→ `EXACT MATCH`

### Seviye B — Güvenli aday eşleşme

Aşağıdaki yardımcı bilgiler birlikte değerlendirilecek:

- normalize edilmiş proje adı
- dosya adı
- müşteri / proje alanı
- sipariş numarası
- tarih
- ortak ekipman referansları

Sonuç:

```text
HIGH CONFIDENCE
MEDIUM CONFIDENCE
REVIEW REQUIRED
NO MATCH
```

### Kritik prensip

**Benzer görünen iki proje otomatik olarak birleştirilmeyecek.**

Özellikle aynı müşterinin aynı tipte birden fazla AHU projesi varsa yanlış eşleştirme, kW karşılaştırmasında zincirleme hata oluşturur.

---

## Faz 5 — Eşleşen projelerin AHU isimlerini eşleştirme

Proje eşleşmesinden sonra ikinci eşleştirme seviyesi başlayacak.

```text
PROJE A
PDF 1                    PDF 2
AHU-01       ↔            AHU-01
AHU-02       ↔            AHU-02
AHU-03       ↔            AHU-03
```

Fakat isimler birebir aynı olmak zorunda değil.

Desteklenecek normalize örnekleri:

```text
AHU-01
AHU01
AHU_01

AHU-EF-01
AHU_EF_01
```

Ayrıca mevcut `PW-02 → PW2` gibi kontrollü ekipman normalizasyonları korunacak.

### AHU eşleştirme sonucu

```text
EXACT
NORMALIZED_MATCH
AMBIGUOUS
ONLY_IN_PDF1
ONLY_IN_PDF2
```

Her eşleşme için kaynak PDF ve kaynak sayfa saklanacak.

---

## Faz 6 — Proje + AHU motor database oluşturma

Bu aşamada mevcut motor motoru kullanılacak; ancak artık tek dosya değil, hiyerarşik yapı üzerinde çalışacak.

```text
Project
└── AHU / Equipment
    ├── PDF 1 motors
    │   ├── Vant 1
    │   ├── Vant 2
    │   ├── Asp 1
    │   ├── Asp 2
    │   └── ...
    │
    └── PDF 2 motors
        ├── Vant 1
        ├── Vant 2
        ├── Asp 1
        ├── Asp 2
        └── ...
```

Özellikle karmaşık projelerde:

```text
2 Supply
2 Return
2 Activation / Reaktivasyon
```

gibi fanların birbirine karışmaması sağlanacak.

**Activation / Reaktivasyon ayrı komponent ailesi olarak korunacak; Aspiratör'e dönüştürülmeyecek.**

---

## Faz 7 — Motor eşleştirme ve kW karşılaştırma

Artık mevcut motor karşılaştırma mantığı proje + AHU seviyesine taşınacak.

Ana anahtar:

```text
project
+ equipment
+ component_type
+ physical_motor_index
```

Örnek:

```text
25END092
AHU-03
Vantilatör
Vant 1
```

PDF 1:

```text
22.0 kW
```

PDF 2:

```text
22.0 kW
```

→ `MATCH`

Diğer sonuçlar:

```text
MISMATCH
ONLY_IN_PDF1
ONLY_IN_PDF2
REVIEW_REQUIRED
```

---

# Faz 8 — Toplu karşılaştırma ekranı

En önemli yeni kullanıcı arayüzü bu olacak.

## Ana ekran

```text
┌─────────────────────────────────────────────────────────────┐
│ PDF KW SELECTOR — TOPLU PROJE KARŞILAŞTIRMA                 │
├─────────────────────────────────────────────────────────────┤
│ PDF: 147     PROJE: 18     AHU: 63     MOTOR: 184          │
├─────────────────────────────────────────────────────────────┤
│ PROJE        AHU       MATCH   FARKLI   PDF1   PDF2 REVIEW │
│ 25END092     AHU-01      6       1       0      0      0    │
│ 25END092     AHU-02      4       0       1      0      0    │
│ 25END093     AHU-01      5       0       0      1      0    │
│ ...                                                         │
└─────────────────────────────────────────────────────────────┘
```

### Filtreler

- Proje
- AHU
- Motor tipi
- MATCH
- MISMATCH
- ONLY PDF1
- ONLY PDF2
- REVIEW
- Güç farkı
- Kaynak PDF

### Detay ekranı

Bir AHU seçildiğinde:

```text
PROJE: 25END092
AHU: AHU-03

Motor      Tip           PDF1      PDF2      Fark      Durum
Vant 1     Vantilatör    22.0      22.0      0.0       MATCH
Vant 2     Vantilatör    22.0      22.0      0.0       MATCH
Asp 1      Aspiratör     15.0      15.0      0.0       MATCH
Asp 2      Aspiratör     15.0      15.0      0.0       MATCH
```

Her satırdan kaynak sayfaya kadar inilebilecek.

---

# Faz 9 — Toplu rapor

Sonuçlar sadece GUI'de gösterilmeyecek.

İlk aşamada:

```text
JSON
CSV
Excel
```

çıktıları planlanıyor.

Rapor seviyeleri:

```text
1. Genel proje özeti
2. Proje → AHU özeti
3. AHU → motor özeti
4. Sadece hatalı motorlar
5. Sadece eşleşmeyen PDF/AHU'lar
6. REVIEW listesi
```

Örnek özet:

```text
TOPLAM PROJE             18
TOPLAM AHU               63
TOPLAM MOTOR            184

MATCH                   169
MISMATCH                  8
ONLY PDF1                 3
ONLY PDF2                 2
REVIEW                    2
```

---

# Faz 10 — Güvenlik ve yanlış eşleşme kontrolü

Çoklu PDF sisteminde en kritik konu yanlış eşleştirme riskidir.

Bu nedenle her seviyede confidence tutulacak:

```text
PDF confidence
Project confidence
AHU confidence
Motor confidence
```

Örneğin:

```text
Project: HIGH
AHU: HIGH
Motor: HIGH
→ otomatik karşılaştır
```

ve:

```text
Project: MEDIUM
AHU: AMBIGUOUS
→ karşılaştırmayı durdur
→ REVIEW_REQUIRED
```

Sistem **yanlış eşleştirip sahte MATCH üretmektense REVIEW üretmeyi tercih edecek.**

---

# Teknik mimari planı

Mevcut modüller korunarak yeni katmanlar eklenecek.

```text
PDF INPUT LAYER
├── pdf_input_manager.py
├── folder_scanner.py
└── pdf_document.py

PROJECT LAYER
├── project_extractor.py
├── project_normalizer.py
└── project_matcher.py

EQUIPMENT LAYER
├── equipment_extractor.py
├── equipment_normalizer.py
└── equipment_matcher.py

MOTOR LAYER
├── stage1_page_discovery.py
├── stage2_pdf_discovery.py
├── motor_database.py
└── motor_compare.py

BATCH LAYER
├── batch_analyzer.py
├── batch_results.py
└── report_export.py

UI LAYER
└── desktop_app.py
```

Yeni katmanlar mevcut motor parser'larını yeniden yazmak yerine onların üzerine kurulacak.

---

# Geliştirme sırası

## Milestone 1 — Multi-PDF Input

```text
[ ] Çoklu PDF seçimi
[ ] Klasör seçimi
[ ] Alt klasör tarama
[ ] Duplicate kontrolü
[ ] PDFDocument modeli
[ ] Dosya listesi GUI
[ ] Testler
```

## Milestone 2 — Project Discovery

```text
[ ] Project Name extractor
[ ] Raw / normalized değerler
[ ] Source page / field
[ ] Confidence
[ ] Project grouping
[ ] Test PDF'leri
```

## Milestone 3 — Project Matching

```text
[ ] Exact match
[ ] Normalized match
[ ] Candidate scoring
[ ] Ambiguous detection
[ ] REVIEW_REQUIRED
[ ] Testler
```

## Milestone 4 — AHU Matching

```text
[ ] PDF içinden equipment listesi
[ ] AHU normalize
[ ] PDF1 ↔ PDF2 AHU matching
[ ] ONLY_IN_PDF1
[ ] ONLY_IN_PDF2
[ ] AMBIGUOUS
[ ] Testler
```

## Milestone 5 — Batch Motor Analysis

```text
[ ] Proje bazında motor database
[ ] AHU bazında motor database
[ ] Mevcut Stage 1 entegrasyonu
[ ] Mevcut Stage 2 entegrasyonu
[ ] Motor comparison
[ ] Review propagation
[ ] Testler
```

## Milestone 6 — Toplu GUI

```text
[ ] Proje listesi
[ ] AHU listesi
[ ] Motor detayları
[ ] Filtreleme
[ ] Durum özetleri
[ ] Kaynak sayfa gösterimi
[ ] Büyük veri setinde performans
```

## Milestone 7 — Raporlama + EXE

```text
[ ] JSON export
[ ] CSV export
[ ] Excel export
[ ] Summary report
[ ] Error report
[ ] Windows EXE
[ ] Gerçek büyük proje testleri
```

---

# Test stratejisi

Yeni sistem sadece tekil örneklerle değil, gerçek karmaşık projelerle test edilecek.

Özellikle şu senaryolar zorunlu test olacak:

```text
✓ 1x1 fan
✓ 2x1 fan
✓ 3x1 fan
✓ Aynı projede birden fazla AHU
✓ Aynı projede Supply + Return + Activation
✓ Return Motor Connections-1 / -2
✓ Aynı kW değerine sahip birden fazla motor
✓ Summary + detail sayfasının duplicate olmaması
✓ Proje adı PDF1/PDF2 arasında farklı formatta
✓ AHU adı AHU-01 / AHU01 / AHU_01
✓ Eksik PDF
✓ Eksik AHU
✓ Fazla PDF
✓ Ambiguous project
✓ Ambiguous AHU
✓ Bozuk PDF
```

## Kalite kuralı

Yeni bir özellik eklendiğinde:

```text
Kod değişikliği
    ↓
Unit test
    ↓
Gerçek PDF testi
    ↓
pytest -q
    ↓
Windows EXE build
    ↓
EXE gerçek PDF testi
```

Eski çalışan motor mantığı yeni toplu sistem uğruna bozulmayacak.

---

# Mevcut modüller

- `stage1_page_discovery.py` — PDF 1 doğru fan bloğu/sayfa ve Rated Power keşfi.
- `motor_database.py` — motor grubunu fiziksel motor kayıtlarına genişletir.
- `stage2_pdf_discovery.py` — PDF 2 elektrik motor bağlantı sayfalarından motor kW keşfi.
- `motor_compare.py` — iki fiziksel motor database'ini motor bazında karşılaştırır.
- `kw_compare.py` — genel/semantik kW alan karşılaştırma yardımcıları.
- `pdf_kw_selector.py` — bağlam duyarlı kW adayı seçimi.
- `desktop_app.py` — mevcut PDF 1 + PDF 2 seçim, analiz ve karşılaştırma arayüzü.
- `tests/test_stage2.py` — PDF 2 bağlantı sayfası, quantity expansion ve karşılaştırma testleri.
- `.github/workflows/build-windows.yml` — testler başarılıysa Windows EXE üretir.

# Yeni hedef mimari

Programın nihai amacı:

```text
KLASÖRLER / PDF'LER
        ↓
PDF HAVUZU
        ↓
PROJE KEŞFİ
        ↓
PROJE EŞLEŞTİRME
        ↓
AHU EŞLEŞTİRME
        ↓
MOTOR DATABASE
        ↓
MOTOR BAZINDA kW KARŞILAŞTIRMA
        ↓
TOPLU SONUÇ EKRANI
        ↓
RAPOR / EXCEL / JSON
```

Bu mimaride mevcut `Stage 1` ve `Stage 2` motor güç keşfi **temel motor olarak korunacak**; yeni geliştirme bunun üzerine orchestration/batch katmanı olarak kurulacak.
