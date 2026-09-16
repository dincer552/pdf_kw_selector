# PDF kW Selector

Engineering PDF'lerinden motor anma gücünü (kW) bulup Project → AHU → Motor zinciri üzerinden karşılaştıran Windows masaüstü uygulaması.

Bu README, **Durum sütunu / MATCH gösterimi** üzerine yapılan kapsamlı kod incelemesinin sonuçlarını ve mevcut mimarinin önemli noktalarını kayıt altına alır. Amaç, bundan sonraki değişikliklerde hesaplama motoru ile GUI gösteriminin birbirine karıştırılmasını önlemektir.

---

## 1. Ana analiz akışı

Uygulamanın temel veri akışı:

```text
PDF1 + PDF2
   ↓
pdf_master_scan.py
   ↓
MasterPDFScan / cache
   ↓
batch_analysis.py
   ↓
Project → AHU eşleşmesi
   ↓
Fiziksel motor kayıtları
   ↓
motor_compare.py
   ↓
MotorComparison.status
   ↓
desktop_app.py
   ↓
Treeview "Durum" sütunu
   ↓
desktop_grouped_app.py
```

### Önemli sonuç

`MATCH` değeri GUI tarafından üretilmiyor. Karşılaştırma katmanından geliyor ve sonuç satırına taşınıyor.

`motor_compare.py` karşılaştırma sonucunda tolerans/kural değerlendirmesine göre `MATCH` veya `MISMATCH` gibi status değerleri üretir. `desktop_app.py` bu `comparison.status` değerini sonuç satırının **Durum** alanına aktarır. `result_grouping.py` proje/AHU gruplaması yaparken status değerini değiştirmez.

Bu nedenle **Durum sütunundaki veri kaynağı ile Durum hücresinin ekranda nasıl çizildiği iki ayrı konudur.**

---

## 2. Durum sütununun gerçek veri kaynağı

### `motor_compare.py`

Motor karşılaştırmasının sonucunda `MotorComparison.status` bulunur.

Temel mantık:

```text
PDF1 motor gücü
       ↕
PDF2 motor gücü
       ↓
karşılaştırma kuralları / tolerans
       ↓
MATCH veya MISMATCH
```

GUI'deki `MATCH` yazısının asıl kaynağı burasıdır.

### `desktop_app.py`

Karşılaştırma nesnesindeki `status`, Treeview satırının Durum alanına aktarılır.

### `result_grouping.py`

Bu katman sadece Project → AHU gruplamasını düzenler, tekrar eden proje/AHU hücrelerini boşaltır ve gruplar arasına spacer satırı koyar. Status değerinin anlamını değiştirmez.

### `desktop_grouped_app.py`

Gruplanmış sonuçları tekrar GUI tablosuna yerleştirir. Dolayısıyla burada da status üretimi yapılmaz; mevcut status gösterilir.

---

## 3. Windows EXE'de görülen `MATCH` neden düz yazı?

Mevcut Windows GUI'de sonuç tablosu Tkinter `ttk.Treeview` kullanıyor.

Normal Treeview hücresine verilen değer:

```text
MATCH
```

şeklinde düz metin olarak çizilebilir.

Repo içinde yeşil/kırmızı badge çizmek için kod bulunmasına rağmen bu kodların tamamı aynı çalışan yolun parçası değildir. Bu ayrım özellikle önemlidir.

---

## 4. Repo içinde bulunan status badge sistemleri

### A) `status_badges.py`

Bu dosya Tkinter Treeview hücrelerinin üzerine badge çizen bağımsız bir overlay sistemi içerir.

Mantığı:

```python
green = status.casefold() == "match"
label = "✓ MATCH" if green else f"✕ {status}"
```

Sonuç:

| Status | Görsel davranış |
|---|---|
| `MATCH` | Yeşil `✓ MATCH` |
| `match` | Yeşil `✓ MATCH` |
| `MISMATCH` | Kırmızı |
| `EBM_PAPST` | Kırmızı |
| `ONLY_IN_PDF1` | Kırmızı |
| `ONLY_IN_PDF2` | Kırmızı |
| `BA kodu eşleşti (BA550)` | Kırmızı |
| diğer tüm metinler | Kırmızı |

Bu dosyada **tam status eşleşmesi** kullanılması önemlidir. Sadece metnin içinde `eşleşti` veya `match` geçmesi yeterli değildir.

### B) `ui_polish.py`

Burada da ikinci bir badge sistemi bulunuyor.

Temel kontrol:

```python
is_match = text.casefold() == "match"
```

ve yeşil/kırmızı arka plan, yazı ve border uygulanıyor.

Bu sistem de status gösterimini kendi başına yönetebilecek durumdadır.

### C) React `StatusBadge.tsx`

React frontend tarafında merkezi `StatusBadge` component'i bulunuyor.

Güncel mantık:

```typescript
const normalizedStatus = status.trim().toUpperCase();
const isMatch = forcedIsMatch !== undefined
  ? forcedIsMatch
  : normalizedStatus === 'MATCH';
```

React tarafında da kural nettir:

```text
sadece gerçek MATCH → yeşil
her şey başka      → kırmızı
```

`ResultsTable.tsx` bu component'i kullanır.

**Ancak Windows PyInstaller EXE'nin giriş noktası React değildir.** Windows build `desktop_grouped_app.py` üzerinden PyInstaller ile oluşturulur. Bu nedenle React'teki badge görünümü Windows Tkinter GUI'sini otomatik olarak etkilemez.

---

## 5. Kritik ayrım: `MATCH` ne anlama geliyor?

`MATCH` her durumda "iki sayının karakter karakter birebir aynı olması" anlamına gelmez.

Karşılaştırma motorunda özel kabul kuralları bulunabilir. Örneğin mevcut kodda bazı mühendislik eşdeğerlikleri kabul edilebilir. İncelenen örnekte `1.1 kW → 1.5 kW` gibi özel bir kural `MATCH` sonucu üretebiliyor.

Bu nedenle GUI'de yeşil badge'in anlamı:

> **Mevcut karşılaştırma kurallarına göre sonuç kabul edildi / MATCH.**

şeklinde düşünülmelidir.

Yeşil badge eklemek, karşılaştırma algoritmasının kurallarını değiştirmemelidir.

---

## 6. VOCLEAN için özel durum

VOCLEAN tablosunda status alanı her zaman motor karşılaştırmasındaki `MATCH` değildir.

Örnek bilgi metinleri:

```text
BA kodu eşleşti (BA550)
PDF2 AHU eşleşmesi yok; ...
```

Bunlar açıklayıcı/iş akışı status metinleridir.

Bu nedenle global badge kuralı şu olmalıdır:

```text
status == MATCH
    → yeşil

status != MATCH
    → kırmızı
```

Böylece:

```text
MATCH
```
ile

```text
BA kodu eşleşti (BA550)
```

birbirine karıştırılmaz.

---

## 7. PDF keşif ve karşılaştırma mimarisi

### `pdf_master_scan.py`

PDF'ler Master Scan seviyesinde okunur ve cache'lenir.

Tek taramada temel olarak:

- Project
- AHU / Unit Reference
- sayfa metinleri
- motor kW
- motor sayısı / grup bilgisi
- motor tipi / rolü
- motor sayfası
- EBM-Papst bilgisi

çıkarılabilir.

Cache anahtarında dosya yolu, modification time ve dosya boyutu kullanılır.

### PDF1 Project / Unit Reference

PDF1 tarafında ekipman keşfi genel `AHU` kelimesine bağlı olmamalıdır. Ana referans:

```text
Unit Reference → karşısındaki değer
```

olmalıdır.

Bu sayede `AHU-KIT` gibi tesadüfi metinler ekipman ID'si olarak yanlışlıkla yakalanmaz. Ekipman tipi `HKS`, `AHU` vb. değişken olabilir.

PDF1 proje keşfinde de sabit `Project` alanı esas alınır.

### PDF1 motor gücü

`stage1_page_discovery.py` motor gücü keşfini özellikle `Rated Power` / `Fan Motor Power` gibi alanlardan yapar.

Örneğin:

```text
Rated Power [kW] 7,500 x (1x1)
```

→ `7.5 kW`

ve fiziksel motor grubu bilgisi korunur.

`2x1` gibi bir grup bilgisi fiziksel motor adedinin oluşturulmasında kullanılır.

### PDF2 motor gücü

PDF2 tarafında koordinat tabanlı keşif de kullanılır. PDF2 Project ve AHU alanları ilk sayfadaki bilinen koordinat bölgelerinden okunabilir.

---

## 8. Project → AHU eşleşmesi

`batch_analysis.py` ana orkestrasyon katmanıdır.

Sıra:

```text
PDF keşfi
  ↓
Project grupları
  ↓
Project eşleşmesi
  ↓
AHU eşleşmesi
  ↓
Motor keşfi
  ↓
Motor karşılaştırması
```

Project eşleşmesinde:

1. normalize edilmiş exact eşleşme,
2. AHU overlap,
3. son çare olarak fuzzy scoring

kullanılır.

Bu sıralama, benzer isimli fakat farklı projelerin yanlışlıkla birleştirilmesini azaltmak için korunmalıdır.

---

## 9. Daha önce düzeltilmiş önemli problemler

### Tkinter background-thread problemi

PDF analizi background worker üzerinde çalışırken Tkinter dialoglarının worker thread'den açılması `TclError` üretebiliyordu.

Çözüm olarak UI dialog işlemleri Tk ana thread'ine marshal edildi.

### Stale EXE / `_file_box` problemi

Eski Python bytecode veya yanlış kaynakla paketleme nedeniyle `_file_box` eksikliği gibi startup problemleri yaşandı.

Build workflow'a stale `__pycache__` / `.pyc` temizliği ve GUI source verification eklendi.

### VOCLEAN proje grubu problemi

VOCLEAN proje seçimi sonrasında normal AHU project grubunun kullanılabilirliğini koruyacak mantık eklendi.

### VOCLEAN unmatched problemi

VOCLEAN için proje override yapıldığında orijinal VOCLEAN kimliğinin kaybolması nedeniyle özel PDF'ler EŞLEŞMEYEN listesine düşebiliyordu.

Özel PDF setleri unmatched listesinden ayrıştırıldı ve orijinal VOCLEAN kimliği korunacak şekilde akış düzenlendi.

### VOCLEAN tablo başlıkları

İstenen başlıklar:

```text
Proje
Seçim PDF
VOClean kW
Seçim PDF Sayfa
Elektrik P. PDF
AHU
Durum
```

Build workflow'daki başlık düzeltmesi idempotent olacak şekilde hazırlanmıştır; kaynak zaten yeni başlıklara sahipse workflow tekrar çalıştığında hata vermemelidir.

---

## 10. Build güvenlik kontrolleri

`.github/workflows/build-windows.yml` içinde paketleme öncesi kaynak kontrolleri ve paketlenmiş EXE startup smoke test'i bulunur.

Temel akış:

```text
checkout
  ↓
stale pyc temizliği
  ↓
Python dependencies
  ↓
kaynak patch / doğrulama
  ↓
py_compile
  ↓
GUI source verification
  ↓
PyInstaller
  ↓
12 saniyelik EXE startup smoke test
  ↓
release asset yayınlama
```

Özellikle daha önce görülen:

```text
KeyError: 'Seçim PDF'
```

startup hatasının release'e çıkmadan yakalanması hedeflenmektedir.

Smoke test EXE'yi başlatır, 12 saniye çalışıp çalışmadığını kontrol eder. EXE hemen kapanırsa build başarısız olur.

> Bu smoke test startup seviyesinde bir kontroldür; PDF'lerle uçtan uca fonksiyonel GUI testi değildir.

---

## 11. Status GUI için hedef mimari

Durum gösterimi tek bir prensibe indirgenmelidir:

```text
                 MotorComparison.status
                         │
                         ▼
                  Durum hücresi
                         │
              ┌──────────┴──────────┐
              │                     │
         status == MATCH       status != MATCH
              │                     │
              ▼                     ▼
       🟢 ✓ MATCH              🔴 ✕ STATUS
```

### Korunacak kural

**Hesaplama motoru ile görsel gösterim ayrılmalıdır.**

Badge sistemi sadece status değerini görselleştirmeli; `MATCH` üretme kurallarını değiştirmemelidir.

---

## 12. Status için eksik test alanı

Mevcut regression testleri gerçek HKS-12 PDF'lerinde motorların keşfedilmesini ve iki motorun `MATCH` olmasını doğrulamaktadır.

Ancak GUI badge çiziminin kendisini doğrulayan ayrı bir test eksikliği vardır.

Önerilen test matrisi:

```text
MATCH                         → green
match                         → green
 MATCH                        → green
MISMATCH                      → red
EBM_PAPST                     → red
ONLY_IN_PDF1                  → red
ONLY_IN_PDF2                  → red
BA kodu eşleşti (BA550)       → red
PDF2 AHU eşleşti; ...         → red
boş status                    → badge yok / özel davranış
```

Böylece sadece hesaplama sonucu değil, **gösterim kuralı da otomatik olarak korunmuş olur.**

---

## 13. Bundan sonraki değişikliklerde temel prensip

Bu doküman oluşturulduğu anda amaç, önce mevcut mimariyi kayıt altına almaktır. Status görünümünde yeni bir değişiklik yapılacaksa ilk kontrol edilecek noktalar:

1. `motor_compare.py` — status nerede üretiliyor?
2. `batch_analysis.py` — status değiştiriliyor mu?
3. `desktop_app.py` — status Treeview'a nasıl aktarılıyor?
4. `desktop_grouped_app.py` — status tekrar nasıl çiziliyor?
5. `status_badges.py` — Tkinter badge sistemi aktif mi?
6. `ui_polish.py` — ikinci bir badge sistemi aktif mi?
7. `src/components/StatusBadge.tsx` — React badge mantığı nedir?
8. `.github/workflows/build-windows.yml` — hangi dosya gerçek EXE'ye giriyor ve build sonrası hangi testler çalışıyor?
9. `tests/` — status ve gerçek PDF regression testleri var mı?

### Ana karar

**Önce mevcut status üretim zinciri korunacak. Görsel problem çözülürken hesaplama/matching algoritmasına gereksiz müdahale edilmeyecek.**

---

## 14. Referans dosyalar

| Dosya | Görevi |
|---|---|
| `motor_compare.py` | Motor karşılaştırması ve status üretimi |
| `batch_analysis.py` | Project → AHU → Motor orkestrasyonu |
| `pdf_master_scan.py` | Master PDF keşfi ve cache |
| `stage1_page_discovery.py` | PDF1 motor/güç keşfi |
| `stage2_pdf_discovery.py` | PDF2 motor keşfi |
| `desktop_app.py` | Ana Tkinter GUI ve sonuç tablosu |
| `desktop_grouped_app.py` | Gruplandırılmış Windows GUI |
| `result_grouping.py` | Project/AHU görsel gruplama |
| `status_badges.py` | Tkinter status badge overlay |
| `ui_polish.py` | Alternatif Tkinter badge / UI polish sistemi |
| `src/components/StatusBadge.tsx` | React status badge |
| `src/components/ResultsTable.tsx` | React sonuç tablosu |
| `tests/test_real_hks12_regression.py` | Gerçek HKS-12 PDF regression testi |
| `tests/test_result_grouping.py` | Sonuç gruplama testleri |
| `.github/workflows/build-windows.yml` | Windows EXE build, smoke test ve yayınlama |

---

## 15. Durum

Bu README **kod değişikliği yapmak yerine mevcut mimariyi ve yapılan analizi belgelemek amacıyla** güncellenmiştir.

Bir sonraki adım, Windows Tkinter tarafında **tek bir status badge sisteminin gerçek çalışan EXE yoluna bağlanması**, ardından status görünümünü doğrudan test eden regression testinin build pipeline'ına eklenmesidir.
