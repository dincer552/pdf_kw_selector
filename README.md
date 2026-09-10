# pdf_kw_selector

Engineering PDF'lerinden **doğru motor anma gücünü (kW) bulup fiziksel motor bazında normalize eden ve iki PDF arasında doğrulayan** motor.

## Güncel durum

Uygulama Project → AHU → Motor sırasıyla çalışır. PDF1 seçim/referans, PDF2 elektrik/üretim dokümanıdır. Motor karşılaştırması fiziksel motor bazındadır; `2x1` iki fiziksel motor anlamına gelir.

### Tanılama / hata logları

Masaüstü uygulamasında **HATA / İŞLEM LOGLARI** sekmesi bulunur. Dosya seçme, PDF okuma, proje/AHU keşfi, motor kW çıkarımı, fiziksel motor üretimi, eşleştirme, kW fark hesapları, JSON kaydetme ve güncelleme/EXE indirme adımları ayrıntılı olarak loglanır. Yakalanmamış hatalarda traceback de kaydedilir.

Windows'ta log dosyası varsayılan olarak:

`%LOCALAPPDATA%\\PDF_KW_Selector\\logs\\pdf_kw_selector.log`

Log dosyası GUI içinden doğrudan açılabilir; log klasörü açılabilir, yenilenebilir ve temizlenebilir. Loglar dönen dosyalar halinde tutulur (2 MB + 5 yedek), böylece programın hata geçmişi sınırsız büyümez.

### Güncelleme

**GÜNCELLEME KONTROL ET** butonu GitHub Releases üzerinden güncel EXE'yi kontrol eder. İndirme Releases asset API endpoint'i üzerinden yapılır, cache-busting uygulanır ve indirilen EXE SHA-256 ile doğrulanır. Güncelleme kontrolü/indirme/değiştirme aşamalarındaki HTTP, ağ, dosya, SHA-256 ve yeniden başlatma hataları loglanır.

## Test seviyesi kuralı

`UNIT TEST PASSED` ≠ `REAL PDF TEST PASSED` ≠ `FULL PIPELINE PASSED` ≠ `EXE TEST PASSED`.

Windows CI her push'ta testleri çalıştırır ve başarılı build'i `latest` release asset'i olarak yayınlar.
