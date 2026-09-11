# pdf_kw_selector

Engineering PDF'lerinden **doğru motor anma gücünü (kW) bulup fiziksel motor bazında normalize eden ve iki PDF arasında doğrulayan** motor.

## Güncel durum

Uygulama Project → AHU → Motor sırasıyla çalışır. PDF1 seçim/referans, PDF2 elektrik/üretim dokümanıdır. Motor karşılaştırması fiziksel motor bazındadır; `2x1` iki fiziksel motor anlamına gelir.

### PDF analiz mimarisi — tamamlandı

Analiz süreci **tek geçişli Master PDF Scan + cache** mimarisine geçirilmiştir.

- [x] **PDF bir kez açılıyor ve sayfalar bir kez okunuyor.** Master scan sayfa metinlerini cache'liyor.
- [x] **Tek taramada proje adı, AHU / `Unit Reference`, motor kW, sayfa, motor tipi/rolü/miktarı çıkarılıyor.**
- [x] **EBM-Papst kontrolü yalnızca PDF1'de yapılıyor.** PDF2'de EBM taraması yapılmıyor.
- [x] **Sonraki Project → AHU → Motor adımları cache kullanıyor; aynı PDF tekrar okunmuyor.**
- [x] **PDF1 ve PDF2 master scan seviyesinde paralel taranıyor.**
- [x] **Güçlü eşleşme anahtarları önce kullanılıyor.** Normalize AHU ve proje ID'leri exact-first eşleştiriliyor; yalnızca kalan adaylarda fuzzy karşılaştırma yapılıyor.
- [x] **Motor/EBM taraması hedefli.** PDF1 EBM kontrolü yalnızca motor sonucu üreten sayfalarda yapılıyor; PDF2'de EBM taraması yok.
- [x] **Pahalı normalizasyon tekrarları azaltıldı.** Master scan sonuçları ve normalize edilmiş anahtarlar downstream işlemlerde yeniden kullanılıyor.
- [x] **GUI ana thread'inin PDF taraması nedeniyle donması kaldırıldı.** Master PDF taraması background worker üzerinde çalışıyor; Tk işlemleri ana thread'e geri dönüyor.

### Performans hedefi — tamamlandı

Amaç yalnızca analizi hızlandırmak değil, **aynı PDF üzerinde aynı işi birden fazla kez yapmayı mimari olarak engellemekti**. Plan tamamlandı:

**Master Scan + Cache → paralel PDF taraması → eşleştirme optimizasyonu → hedefli motor/EBM taraması → GUI worker thread.**

Mevcut gerçek PDF davranışı korunuyor. Özellikle `HKS-12` / `HKS_12` normalize eşleşmesi, `Unit Reference` önceliği ve `AHUKit` gibi yanlış ekipman tespitlerinin engellenmesi regression testleriyle korunuyor.

### Tanılama / hata logları

Masaüstü uygulamasında **HATA / İŞLEM LOGLARI** sekmesi bulunur. Dosya seçme, PDF okuma, proje/AHU keşfi, motor kW çıkarımı, fiziksel motor üretimi, eşleştirme, kW fark hesapları, JSON kaydetme ve güncelleme/EXE indirme adımları ayrıntılı olarak loglanır. Yakalanmamış hatalarda traceback de kaydedilir.

Windows'ta log dosyası varsayılan olarak:

`%LOCALAPPDATA%\\PDF_KW_Selector\\logs\\pdf_kw_selector.log`

Log dosyası GUI içinden doğrudan açılabilir; log klasörü açılabilir, yenilenebilir ve temizlenebilir. Loglar dönen dosyalar halinde tutulur (2 MB + 5 yedek), böylece programın hata geçmişi sınırsız büyümez.

### Güncelleme

**GÜNCELLEME KONTROL ET** butonu GitHub Releases üzerinden güncel EXE'yi kontrol eder. İndirme Releases asset API endpoint'i üzerinden yapılır, cache-busting uygulanır ve indirilen EXE SHA-256 ile doğrulanır. Güncelleme kontrolü/indirme/değiştirme aşamalarındaki HTTP, ağ, dosya, SHA-256 ve yeniden başlatma hataları loglanır.

## Test seviyesi kuralı

`UNIT TEST PASSED` ≠ `REAL PDF TEST PASSED` ≠ `FULL PIPELINE PASSED` ≠ `EXE TEST PASSED`.

Windows CI her push'ta testleri çalıştırır ve başarılı build'i `latest` release asset'i olarak yayınlar. Performans mimarisi tamamlandıktan sonra gerçek PDF regression kapsamı `HKS-12` için PDF1 `7.5 + 4.0 kW`, PDF2 `7.5 + 4.0 kW`, iki fiziksel motor ve iki `MATCH` sonucunu doğrular.
