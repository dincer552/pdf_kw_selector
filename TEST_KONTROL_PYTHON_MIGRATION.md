# TEST KONTROL → PYTHON MIGRATION

Bu doküman, `umut-test-pro` içindeki mevcut **TestKontrolProg (C#)** uygulamasının, `pdf_kw_selector` içine **Python/Tkinter ile tek uygulama** olarak taşınmasını takip eder.

Amaç, mevcut PDF_KW_SELECTOR altyapısını bozmadan Test Kontrol fonksiyonlarını ayrı bir EXE yerine uygulama içinde `TEST KONTROL` sekmesinde çalıştırmaktır.

## Ana hedef mimari

```text
PDF_KW_SELECTOR.exe
   ├── DANFOS
   ├── EBM-PAPST
   ├── VOCLEAN
   ├── SYSRECO
   ├── diğer mevcut sekmeler
   └── TEST KONTROL
          ├── Genel
          ├── Fan Kontrol
          ├── Modüller
          ├── Sensorler
          ├── Damper Kontrol
          ├── Filtre Kontrol
          ├── User
          └── Rapor
```

## Değişmez kurallar

1. Mevcut PDF analiz, eşleşme, status, GUI ve build altyapısı korunacak.
2. Her aşama küçük ve test edilebilir şekilde uygulanacak.
3. Her işlemden sonra bu README okunacak.
4. Bir aşama gerçekten tamamlanıp test/build doğrulaması geçmeden sonraki aşamaya geçilmeyecek.
5. Tamamlanan aşamanın kutusu `☐` → `☑` yapılacak.
6. Başarısız veya eksik aşama `☐` olarak kalacak; başarısızlığı gizlemek için işaret konulmayacak.
7. C# uygulaması referans davranış olarak korunacak; Python karşılığı doğrulanmadan C# bağımlılığı kaldırılmayacak.
8. Son aşamalarda C# / MSBuild / harici `umut-test-pro` build bağımlılığı tamamen kaldırılacak.

---

# AŞAMA TAKİP LİSTESİ

## Faz 0 — Referansın dondurulması

- ☐ `dincer552/umut-test-pro` mevcut C# yapısı ve davranışları referans olarak belirlenecek.
- ☐ `Datas.cs`, `Form1`, `FanKontrol`, `DamperKontrol`, `FiltreKontrol`, `Moduller`, `Sensorler`, `UserControl` ve rapor üretimi incelenecek.
- ☐ Mevcut fonksiyon listesi çıkarılacak.

**Tamamlanma şartı:** C# uygulamasındaki taşınacak fonksiyonların listesi netleşmiş olacak.

## Faz 1 — Python Test Control veri modeli

- ☐ `test_control/` Python paketi oluşturulacak.
- ☐ C# `Datas.cs` karşılığı Python veri modeli oluşturulacak.
- ☐ Global/static veri yerine mümkün olduğunca açık bir Python state/model yapısı kullanılacak.
- ☐ Mevcut alanların isimleri ve anlamları korunacak.

**Tamamlanma şartı:** Python tarafında Test Kontrol verisi tutulabiliyor ve temel testler geçiyor.

## Faz 2 — TEST KONTROL sekmesi

- ☐ `desktop_grouped_app.py` içine mevcut Notebook yapısını bozmadan `TEST KONTROL` sekmesi eklenecek.
- ☐ İlk etapta sekme açılacak ve çalışır durumda olacak.
- ☐ Harici C# EXE başlatılmayacak; hedef in-process Python arayüzüdür.
- ☐ Mevcut PDF sekmeleri ve status sistemi etkilenmeyecek.

**Tamamlanma şartı:** PDF_KW_SELECTOR içinde TEST KONTROL sekmesi açılıyor ve mevcut sekmeler/regression testleri bozulmuyor.

## Faz 3 — Genel / Ana ekran

- ☐ Order No
- ☐ Proje Adı
- ☐ AHU Adı
- ☐ kontrol butonları/statusları
- ☐ Notlar
- ☐ BACnet / Modbus alanları
- ☐ mevcut kullanıcı alanı için temel bağlantı

**Tamamlanma şartı:** C# ana ekranındaki temel bilgi akışı Python sekmesinde çalışıyor.

## Faz 4 — Fan Kontrol

- ☐ Fan tipi seçimi
- ☐ Supply fan sayısı
- ☐ Return fan sayısı
- ☐ Supply airflow
- ☐ Return airflow
- ☐ Debi Kontrol (%25)
- ☐ Basınç Kontrol
- ☐ Kaydet

**Tamamlanma şartı:** Fan verileri Python modeline doğru kaydediliyor ve tekrar gösterilebiliyor.

## Faz 5 — Damper Kontrol

- ☐ Fresh Damper
- ☐ Supply Damper
- ☐ Return Damper
- ☐ Exhaust Damper
- ☐ Mix Damper
- ☐ Bypass Damper
- ☐ Damper sayıları ve Kaydet işlemleri

**Tamamlanma şartı:** Altı damper grubunun tamamı veri modeline doğru aktarılıyor.

## Faz 6 — Filtre Kontrol

- ☐ FreshF7
- ☐ FreshG4
- ☐ ReturnG4
- ☐ SupplyF9
- ☐ FreshF9
- ☐ ReturnF7
- ☐ FreshM5
- ☐ FreshG2
- ☐ FreshF4
- ☐ ReturnM5
- ☐ ReturnF9
- ☐ ReturnG2
- ☐ SupplyM5
- ☐ SupplyG4
- ☐ SupplyF7
- ☐ SupplyG2
- ☐ HepaFilter
- ☐ H13Filter
- ☐ Kaydet

**Tamamlanma şartı:** Filtre seçimleri C# davranışıyla uyumlu şekilde kaydediliyor.

## Faz 7 — Modüller

- ☐ Rotor
- ☐ Rotor Oransal / On-Off
- ☐ RunAround Batarya
- ☐ DX Batarya + kademe sayısı
- ☐ Nemlendirici + kademe sayısı
- ☐ Elektrikli Isıtıcı + grid
- ☐ Isıtma Vanası 1
- ☐ Soğutma Vanası 1
- ☐ Soğutma Vanası 2
- ☐ Isıtma Vanası 2
- ☐ Faz Koruma Normal
- ☐ TBŞ Kontrol
- ☐ Kapı Switch
- ☐ Yangın Alarmı
- ☐ Acil Stop Alarmı
- ☐ Donma Termostatı Alarmı
- ☐ Yüksek Sıcaklık Ter. Kontrol
- ☐ ChangeOver Valve
- ☐ Room BMS
- ☐ Temp Average En

**Tamamlanma şartı:** C# validasyonları dahil modül seçimleri Python tarafında karşılanıyor.

## Faz 8 — Sensörler: arayüz ve manuel veri

- ☐ Fresh Air Sensor: Sıcaklık / Nem / CO2
- ☐ Supply Air Sensor: Sıcaklık / Nem / CO2
- ☐ Return Air Sensor: Sıcaklık / Nem / CO2
- ☐ Exhaust Air Sensor: Sıcaklık / Nem / CO2
- ☐ AfterCoil Air Sensor: Sıcaklık / Nem / CO2
- ☐ Mix Air Sensor: Sıcaklık / Nem / CO2
- ☐ Room Temp Sensor: Sıcaklık / Nem
- ☐ Room Temp Sensor 2: Sıcaklık
- ☐ Return CO2 Sensor: CO2
- ☐ Water Temp Sensor: Sıcaklık
- ☐ Return CO2 Air Sensor: Sıcaklık / CO2
- ☐ Kaydet

**Tamamlanma şartı:** Sensör ekranı çalışıyor ve manuel değerler modelde tutuluyor.

## Faz 9 — C600 / GenericJSON bağlantısı

- ☐ C600 USB → SCOPE → local TCP tunnel mimarisi doğrulanacak.
- ☐ Local Climatix JSON API bağlantısı yapılacak.
- ☐ Basic Authentication yapılandırılacak; kimlik bilgileri kaynak koda sabit yazılmayacak.
- ☐ `GenericJSON.csv` mapping dosyası kullanılacak.
- ☐ İlk canlı okuma olarak `SUPPLY_AIR_TEMP` doğrulanacak.

**Tamamlanma şartı:** Gerçek C600 bağlantısından Supply Air sıcaklığı Python uygulamasında okunuyor.

## Faz 10 — Tüm sensör canlı okumaları

- ☐ Fresh Air mappings
- ☐ Supply Air mappings
- ☐ Return Air mappings
- ☐ Exhaust Air mappings
- ☐ AfterCoil Air mappings
- ☐ Mixing Air mappings
- ☐ Room Temp mappings
- ☐ Room Hum mappings
- ☐ Room CO2 mappings
- ☐ Water Temp mapping
- ☐ diğer mevcut GenericJSON sensörleri

**Tamamlanma şartı:** C# uygulamasındaki canlı sensör okuma kapsamı Python tarafında karşılanıyor.

## Faz 11 — User / imza sistemi

- ☐ User ekleme
- ☐ User silme
- ☐ User listesi
- ☐ Ad Soyad
- ☐ Fotoğraf / imza görseli
- ☐ mevcut kullanıcı ayarlarının Python karşılığı

**Tamamlanma şartı:** Kullanıcı seçimi ve rapor için kullanıcı bilgisi Python modeline bağlanıyor.

## Faz 12 — Excel Test Raporu

- ☐ Mevcut `Test_Report_BACnet_Modbus.xlsx` şablonu korunacak.
- ☐ `openpyxl` ile C# rapor alanlarının karşılığı oluşturulacak.
- ☐ Fan / modül / damper / filtre / sensör / not / kullanıcı alanları aktarılacak.

**Tamamlanma şartı:** Python Excel raporu C# raporundaki gerekli bilgileri üretiyor.

## Faz 13 — PDF Test Raporu

- ☐ Mevcut PDF şablonu korunacak.
- ☐ C# PDF koordinatları Python'a taşınacak.
- ☐ `reportlab` / `pypdf` tabanlı üretim uygulanacak.
- ☐ Proje, AHU, fan, modül, damper, filtre, sensör, not ve kullanıcı bilgileri aktarılacak.

**Tamamlanma şartı:** Python PDF raporu mevcut rapor formatının gerekli içeriğini üretir.

## Faz 14 — PDF → TEST KONTROL veri aktarımı

- ☐ PDF_KW_SELECTOR'dan Project bilgisi alınacak.
- ☐ AHU / Unit Reference bilgisi alınacak.
- ☐ Motor/fan bilgileri uygun Test Kontrol alanlarına bağlanacak.
- ☐ Aynı uygulama içindeki state/model kullanılacak.

**Tamamlanma şartı:** PDF analizi sonucu Test Kontrol ekranında ilgili bilgiler otomatik doldurulabiliyor.

## Faz 15 — Entegrasyon regression testleri

- ☐ Mevcut PDF regression testleri geçecek.
- ☐ HKS-12 regression korunacak.
- ☐ TEST KONTROL sekmesi açılış testi geçecek.
- ☐ PDF analizinden TEST KONTROL'e veri aktarımı test edilecek.
- ☐ Mevcut status sistemi değişmeden çalışacak.
- ☐ PyInstaller Windows EXE startup smoke test geçecek.

**Tamamlanma şartı:** Yeni Python Test Kontrol entegrasyonu mevcut PDF uygulamasını bozmadan çalışıyor.

## Faz 16 — C# bağımlılığının kaldırılması

- ☐ `TestKontrolProg` C# build bağımlılığı kaldırılacak.
- ☐ `umut-test-pro` checkout/pin adımları kaldırılacak.
- ☐ MSBuild bağımlılığı kaldırılacak.
- ☐ `test_control_launcher.py` harici EXE başlatma mantığı kaldırılacak.
- ☐ Eski C# dosyaları PDF build paketine dahil edilmeyecek.
- ☐ GitHub Actions sadeleştirilecek.

**Tamamlanma şartı:** PDF_KW_SELECTOR tek Python uygulaması olarak Test Kontrol dahil build ediliyor.

---

# Her aşama sonrası zorunlu kontrol

Her commit/işlemden sonra sıra şu şekilde ilerleyecek:

```text
1. Değişikliği yap
        ↓
2. README'yi oku
        ↓
3. O aşamanın tamamlanma şartlarını kontrol et
        ↓
4. Test / build çalıştır
        ↓
5. Başarılıysa ilgili ☐ → ☑ yap
        ↓
6. Commit et
        ↓
7. README'yi tekrar oku
        ↓
8. Sonraki aşamaya geç
```

Bir aşama başarısızsa:

```text
☐ Aşama tamamlanmadı
   ↓
Sorunu düzelt
   ↓
Tekrar test/build
```

**Başarısız aşama işaretlenmeyecek ve sonraki aşamaya geçilmeyecek.**

---

# Şu anki durum

**Başlangıç:** Tüm aşamalar `☐` durumunda.

İlk uygulanacak iş: **Faz 0 → Faz 1 → Faz 2**.

Bu dosya, Python Test Kontrol entegrasyonunun ana yol haritasıdır. Her tamamlanan aşamada güncellenmelidir.
