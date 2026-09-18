# PDF kW Selector

Engineering PDF'lerinden motor anma gücünü (kW) bulup **Project → AHU → Motor** zinciri üzerinden karşılaştıran Windows masaüstü uygulaması.

## 1. Temel analiz akışı

```text
PDF1 + PDF2
   ↓
pdf_master_scan.py
   ↓
batch_analysis.py
   ↓
Project → AHU eşleşmesi
   ↓
Fiziksel motor kayıtları
   ↓
motor_compare.py
   ↓
status.py
   ↓
MotorComparison.status
   ↓
desktop_app.py / desktop_grouped_app.py
   ↓
Durum hücresi
```

PDF taraması Master Scan + cache mantığıyla yapılır. Project, Unit Reference/AHU, motor kW, sayfa, motor rolü ve özel PDF bilgileri mümkün olduğunca aynı taramada çıkarılır.

---

# 2. STATUS MİMARİSİ — TEK ÇATI

Status konusunda daha önce oluşan dağınık yapı temizlenmiştir.

## Tek kaynak: `status.py`

Artık status kararının merkezi:

```text
status.py
   ├── status sabitleri
   ├── status normalizasyonu
   ├── MATCH kontrolü
   ├── motor status kararı
   └── Windows Tkinter status gösterimi
```

### Status sabitleri

```text
MATCH
MISMATCH
EBM_PAPST
ONLY_IN_PDF1
ONLY_IN_PDF2
```

### Karar kuralı

Motor karşılaştırmasında status'u artık doğrudan `motor_compare.py` üretmez. `motor_compare.py`, merkezi `status.decide_motor_status()` fonksiyonuna başvurur.

```text
PDF1 motor + PDF2 motor
          ↓
   status.decide_motor_status()
          ↓
       tek karar
          ↓
 MotorComparison.status
```

Böylece status kararının ikinci bir kopyası oluşmaz.

### Yeşil/kırmızı kuralı

Tek ve kesin kural:

```text
status == MATCH
    → 🟢 yeşil

status != MATCH
    → 🔴 kırmızı
```

Örneğin:

| Status | Görünüm |
|---|---|
| `MATCH` | 🟢 `✓ MATCH` |
| `match` | 🟢 `✓ MATCH` |
| `MISMATCH` | 🔴 `✕ MISMATCH` |
| `EBM_PAPST` | 🔴 `✕ EBM_PAPST` |
| `ONLY_IN_PDF1` | 🔴 `✕ ONLY_IN_PDF1` |
| `ONLY_IN_PDF2` | 🔴 `✕ ONLY_IN_PDF2` |
| `BA kodu eşleşti (BA550)` | 🔴 |
| `PDF2 AHU eşleşti; ...` | 🔴 |

Metnin içinde `eşleşti`, `match` veya benzeri bir kelimenin geçmesi sonucu yeşile çevirmiyoruz. **Sadece gerçek status değeri `MATCH` ise yeşil.**

---

# 3. Temizlenen eski status sistemleri

Daha önce aynı işi farklı yerlerde yapan Python yapıları vardı:

- `status_badges.py`
- `ui_polish.py` içindeki status badge sistemi

Windows masaüstü uygulamasında artık bunların yerine yalnızca `status.py` kullanılır.

Silinen dosyalar:

```text
status_badges.py   → kaldırıldı
ui_polish.py       → kaldırıldı
```

`desktop_grouped_app.py` artık doğrudan:

```python
from status import install_status_display
```

kullanıyor ve uygulama oluşturulduktan sonra merkezi status renderer'ı kuruyor.

React frontend ayrı bir prototip/arayüzdür; Windows PyInstaller EXE'nin giriş noktası değildir. Windows uygulamasının gerçek status davranışı `status.py` tarafından belirlenir.

---

# 4. Status kararındaki özel kurallar

Mevcut mühendislik kuralları korunmuştur.

### Normal karşılaştırma

```text
|PDF1 kW - PDF2 kW| <= tolerance
        ↓
      MATCH
```

aksi durumda `MISMATCH`.

### 1.1 → 1.5 özel eşdeğerliği

Mevcut özel kural korunmaktadır:

```text
PDF1 = 1.1 kW
PDF2 = 1.5 kW
       ↓
     MATCH
```

Bu özel kural yalnızca bu eşdeğerlik içindir.

### EBM-Papst

```text
PDF1 Model Brand = EBM-Papst
       ↓
EBM_PAPST
```

Normal motor kW karşılaştırması yapılmaz; özel EBM görünümü korunur.

### Tek taraflı motor

```text
PDF1 yok → ONLY_IN_PDF2
PDF2 yok → ONLY_IN_PDF1
```

---

# 5. Status üretimi ile GUI gösterimi

`status.py` tek merkezde iki ilgili işi tanımlar:

1. Status kararının kuralları
2. Status'un Windows GUI'de nasıl gösterileceği

GUI renderer status'u değiştirmez; sadece görselleştirir.

```text
                     status.py
              ┌────────────┴────────────┐
              │                         │
       karar fonksiyonu             renderer
              │                         │
              ▼                         ▼
       MATCH/MISMATCH              yeşil/kırmızı
```

---

# 6. PDF keşif mimarisi

## `pdf_master_scan.py`

PDF'ler cache'li Master Scan üzerinden okunur.

Çıkarılabilen bilgiler:

- Project
- Unit Reference / AHU
- sayfa metinleri
- motor kW
- motor sayısı / grup bilgisi
- motor tipi / rolü
- motor sayfası
- EBM-Papst bilgisi

## PDF1 Unit Reference

PDF1 ekipman keşfinde genel `AHU`/`HKS` kelime taraması yerine `Unit Reference` alanının karşısındaki değer esas alınır.

Bu sayede `AHU-KIT` gibi tesadüfi metinler ekipman ID'si olarak yakalanmaz.

Ekipman tipi değişken olabilir: `HKS`, `AHU`, `FAHU` vb.

## PDF1 Project

PDF1 proje keşfinde `Project` alanının karşısındaki değer esas alınır.

## PDF1 motor gücü

`stage1_page_discovery.py` özellikle `Rated Power` / `Fan Motor Power` alanlarını kullanır.

Örneğin:

```text
Rated Power [kW] 7,500 x (1x1)
```

→ `7.5 kW`

`NxM` grup bilgisi fiziksel motor kayıtlarının oluşturulmasında korunur.

## PDF2

PDF2 tarafında Project/AHU koordinat alanları ve koordinat tabanlı motor keşfi kullanılabilir.

---

# 7. Project → AHU → Motor eşleşmesi

`batch_analysis.py` ana orkestrasyon katmanıdır.

```text
PDF keşfi
  ↓
Project grupları
  ↓
Project eşleşmesi
  ↓
AHU eşleşmesi
  ↓
Fiziksel motor kayıtları
  ↓
status.decide_motor_status()
```

Eşleşme mantığında güçlü anahtarlar önce kullanılır:

1. normalize edilmiş exact eşleşme
2. AHU overlap
3. gerektiğinde fuzzy scoring

---

# 8. VOCLEAN / EBM / SYSRECO

Özel PDF türleri normal motor sonuçlarından ayrı sekmelerde gösterilir.

### VOCLEAN

VOCLEAN proje seçimi ve özel PDF sınıflandırması korunur.

VOCLEAN açıklaması:

```text
BA kodu eşleşti (BA550)
```

gibi bir metin olabilir. Bu metin **status == MATCH değildir** ve merkezi badge kuralı nedeniyle kırmızı görünür.

### EBM-Papst

EBM-Papst PDF1 dosyaları ayrı görünümde tutulur. Normal kW karşılaştırması yapılmaz.

### SYSRECO

SYSRECO PDF'leri ayrı sınıflandırılır ve özel tab üzerinden gösterilir.

### EŞLEŞMEYEN PDF'LER

Özel PDF'ler EŞLEŞMEYEN listesine yanlışlıkla düşmemelidir. PDF sınıflandırma kontrolü bu ayrımı doğrular.

---

# 9. Daha önce düzeltilmiş önemli problemler

### Tkinter background-thread problemi

Tkinter dialogları background worker thread'den açıldığında `TclError` oluşabiliyordu. UI dialog işlemleri ana Tk thread'ine taşındı.

### Stale EXE / `_file_box`

Stale `__pycache__` / `.pyc` nedeniyle yanlış kaynakla paketleme ihtimaline karşı build sırasında bytecode temizliği ve source verification bulunur.

### VOCLEAN proje grubu

VOCLEAN proje override sonrasında normal AHU grubunun kaybolmasını önleyen mantık korunur.

### VOCLEAN unmatched

VOCLEAN override sonrasında özel PDF'nin EŞLEŞMEYEN listesine düşmesini önleyen özel PDF sınıflandırması korunur.

### VOCLEAN başlıkları

Hedef başlıklar:

```text
Proje
Seçim PDF
VOClean kW
Seçim PDF Sayfa
Elektrik P. PDF
AHU
Durum
```

Build workflow bu başlık değişikliğini idempotent şekilde uygular.

---

# 10. Regression testleri

Yeni `tests/test_status.py` ile status kararının tek merkezden geldiği doğrulanır.

Test edilenler:

```text
MATCH                         → yeşil kabul
match                         → yeşil kabul
MISMATCH                      → kırmızı kabul
EBM_PAPST                     → kırmızı kabul
ONLY_IN_PDF1                  → kırmızı kabul
ONLY_IN_PDF2                  → kırmızı kabul
BA kodu eşleşti (BA550)       → kırmızı kabul
PDF2 AHU eşleşti; ...         → kırmızı kabul
```

Ayrıca merkezi karar fonksiyonu için normal MATCH, normal MISMATCH, 1.1 → 1.5 özel eşdeğerliği, EBM-Papst, yalnızca PDF1 ve yalnızca PDF2 test edilir.

Gerçek HKS-12 regression testi korunur.

---

# 11. Windows build güvenlik akışı

`.github/workflows/build-windows.yml`:

```text
checkout
  ↓
stale pyc temizliği
  ↓
dependencies
  ↓
pytest regression testleri
  ↓
VOCLEAN / özel workflow patchleri
  ↓
central status source verification
  ↓
PyInstaller
  ↓
12 saniyelik EXE startup smoke test
  ↓
release
```

Release yayınlanmadan önce:

```text
pytest geçti mi?
        ↓
source verification geçti mi?
        ↓
EXE oluştu mu?
        ↓
EXE 12 saniye açık kaldı mı?
        ↓
EVET → release
HAYIR → build başarısız
```

Smoke test startup seviyesindedir; gerçek PDF analiziyle tam uçtan uca GUI testi değildir.

---

# 12. Bundan sonraki temel kural

Status ile ilgili yeni kod yazarken **ikinci bir status karar sistemi oluşturulmayacak.**

Tek giriş noktası:

```python
from status import decide_motor_status, is_match_status
```

Tek Windows gösterim noktası:

```python
from status import install_status_display
```

Görsel kural:

```text
MATCH       → 🟢 yeşil
her şey     → 🔴 kırmızı
```

Hesaplama kuralları ile görsel renklerin birbirine karıştırılmaması temel mimari prensiptir.

---

# GitHub yazma testi

Bu bölüm, GitHub repository üzerinde doğrudan README yazma yetkisinin test edilmesi için eklendi.

Test tarihi: 18.09.2026

Amaç: README.md dosyasına doğrudan değişiklik yapılıp commit oluşturulabildiğini doğrulamak.
