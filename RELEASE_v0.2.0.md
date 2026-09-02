# PDF kW Selector v0.2.0 — Windows Test Release

## Bu sürüm

İlk test edilebilir masaüstü arayüzü.

### Özellikler
- PDF 1 seçme
- Offline PDF tarama
- `Anma gücü [kW]` alanını hedefleme
- `Supply air` → Vantilatör
- `Return air` → Aspiratör
- `1x1` → 1 motor
- `2x1` → 2 motor
- `3x1` → 3 motor
- Motorları Vant 1 / Vant 2 / Asp 1 / Asp 2 şeklinde listeleme
- Bulunan kW, grup, sayfa ve güven bilgisini gösterme
- Analiz sonucunu JSON olarak kaydetme

## Bu sürümde henüz yok
- PDF 2 analizi
- PDF 1 ↔ PDF 2 karşılaştırması
- Çoklu AHU için tam blok eşleştirme
- Final rapor

## Windows EXE
GitHub Actions, `desktop_app.py` dosyasını PyInstaller ile Windows `.exe` olarak paketler ve workflow artifact olarak yayınlar.

## Test senaryosu
Örnek PDF:

`Supply air` + `Anma gücü [kW] 3,000 x (1x1)`

Beklenen:

`Vant 1 → 3.0 kW → Sayfa 6 → HIGH`
