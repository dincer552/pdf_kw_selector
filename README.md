# pdf_kw_selector

Engineering PDF'lerinden **doğru motor anma gücünü (kW) bulup fiziksel motor bazında normalize eden ve iki PDF arasında doğrulayan** motor.

## v0.2.3 — Motor gücü eşleştirme düzeltmesi

Bu sürüm, v0.2.2 CI testlerindeki 5 hatayı giderir ve Stage 1 motor keşfini daha sağlam hale getirir.

### Bu sürümde düzeltilenler

- `Supply Fan Motor Power`, `Fan Motor`, `Motor Power`, `Motor Gücü`, `Anma gücü`, `Rated Power` semantik alanları birlikte tanınır.
- Türkçe karakterler (`ü/ğ/ı/ö/ş/ç`) ASCII-normalize edilerek PDF metinlerindeki encoding farklılıklarına karşı eşleştirme güçlendirilir.
- `Unit Total Power`, `Cooling/Heating Capacity`, `Shaft Power` ve VSD güçleri motor anma gücü yerine seçilmez.
- Fan motoru seçimi artık 140 karakterlik çevresel metin nedeniyle yanlışlıkla aggregate alan olarak reddedilmez; aggregate kontrolü değerinin bulunduğu satır üzerinden yapılır.
- `Supply air → Vantilatör`, `Return air → Aspiratör`, `Exhaust air → Aspiratör` korunur.
- `1x1`, `2x1`, `3x1` grup bilgisi korunur; fiziksel motorlar ayrı kayda genişletilir.
- Database liste sırası: `Vant 1`, `Vant 2`, ardından `Asp 1`, `Asp 2`... şeklinde deterministik hale getirildi.
- Page discovery'de `explicit rated power` işareti artık test edilebilir sabit bir marker'dır.

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
Rated Power [kW] 3,000 x (1x1)
→ Vant 1 = 3.0 kW

Rated Power [kW] 15,000 x (2x1)
→ Asp 1 = 15.0 kW
→ Asp 2 = 15.0 kW
```

Kritik nokta: karşılaştırmanın hedefi **motor Rated Power / Anma gücü** alanıdır. `Unit Total Power`, kapasite, shaft power veya VSD değerleri motor gücü olarak kullanılmaz.

## Akış

```text
PDF 1
  ↓
Doğru fan sayfasını bul
  ↓
Ekipman + hava yönü + Rated Power
  ↓
1x1 / 2x1 / 3x1 → fiziksel motor database
  ↓
PDF 2'de aynı motorları bul
  ↓
Motor bazında kW karşılaştır
  ↓
MATCH / MISMATCH / NOT_FOUND / AMBIGUOUS / REVIEW_REQUIRED
```

## Mevcut modüller

- `stage1_page_discovery.py` — doğru fan bloğu/sayfa ve Rated Power keşfi.
- `motor_database.py` — motor grubunu fiziksel motor kayıtlarına genişletir.
- `local_database.py` — normalize edilmiş motorları SQLite'ta saklar.
- `kw_compare.py` — semantik alan bazlı kW karşılaştırması.
- `pdf_kw_selector.py` — bağlam duyarlı motor gücü adayı seçimi.
- `desktop_app.py` — Windows offline Stage 1 test arayüzü.
- `.github/workflows/build-windows.yml` — pytest başarılıysa Windows EXE üretir.

## v0.2.3 CI hedefi

```text
pytest -q
↓
29 test PASS
↓
PyInstaller
↓
PDF_KW_Selector_v0.2.3.exe
```

## Sonraki faz

### Faz 2 — PDF 2

- PDF 1 database kayıtlarını hedefle.
- PDF 2'de aynı ekipmanı bul.
- Aynı komponenti ve fiziksel motor indeksini eşleştir.
- PDF 2 database'ini oluştur.

### Faz 3 — Karşılaştırma

- İki normalize database'i karşılaştır.
- Motor bazında `MATCH / MISMATCH` üret.
- `NOT_FOUND / AMBIGUOUS / REVIEW_REQUIRED` durumlarını yönet.
- Tolerans ve kaynak sayfasını sonuçlara ekle.
