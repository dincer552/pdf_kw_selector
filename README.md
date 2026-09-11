# pdf_kw_selector

Engineering PDF'lerinden **doğru motor anma gücünü (kW) bulup fiziksel motor bazında normalize eden ve iki PDF arasında doğrulayan** motor.

## Güncel durum

Uygulama Project → AHU → Motor sırasıyla çalışır. PDF1 seçim/referans, PDF2 elektrik/üretim dokümanıdır. Motor karşılaştırması fiziksel motor bazındadır; `2x1` iki fiziksel motor anlamına gelir.

### PDF analiz mimarisi — performans planı

Analiz sürecinde aynı PDF'nin tekrar tekrar açılıp taranması kaldırılacaktır. Hedef mimari **tek geçişli Master PDF Scan + cache** yapısıdır:

1. **PDF bir kez açılacak ve sayfalar bir kez okunacak.**
2. Aynı taramada mümkün olan tüm bilgiler çıkarılacak:
   - Proje adı
   - AHU / `Unit Reference` / ekipman adı
   - Motor anma gücü (kW)
   - Sayfa numarası ve ham metin referansları
   - Motor tipi / rolü ve fiziksel motor miktarı
   - **EBM-Papst kontrolü yalnızca PDF1'de** yapılacak; PDF2'de EBM taraması yapılmayacak.
3. Sonraki Project → AHU → Motor eşleştirme adımları tekrar PDF okumak yerine bu cache'deki sonuçları kullanacak.
4. PDF1 ve PDF2 birbirinden bağımsız olduğu için **PDF seviyesinde paralel tarama** değerlendirilecek.
5. Güçlü eşleşme anahtarları (`Unit Reference`, normalize edilmiş AHU ID vb.) önce kullanılarak gereksiz karşılaştırmalar azaltılacak.
6. Motor taraması mümkün olduğunca ilgili sayfalara daraltılacak; tüm PDF'nin tekrar taranması yapılmayacak.
7. Metin normalizasyonu ve benzeri pahalı işlemler aynı veri üzerinde tekrar edilmeyecek.
8. Analiz Tkinter ana thread'ini bloklamayacak şekilde worker/background işlemine taşınacak. Bu CPU süresini doğrudan azaltmasa da GUI'nin analiz sırasında donmasını önleyecek.

### Performans hedefi

Amaç yalnızca analizi hızlandırmak değil, **aynı PDF üzerinde aynı işi birden fazla kez yapmayı mimari olarak engellemek**. Öncelik sırası:

**Master Scan + Cache → paralel PDF taraması → eşleştirme optimizasyonu → hedefli motor/EBM taraması → GUI worker thread.**

Bu değişiklikler yapılırken mevcut gerçek PDF davranışı korunacak. Özellikle `HKS-12` / `HKS_12` normalize eşleşmesi, `Unit Reference` önceliği ve `AHUKit` gibi yanlış ekipman tespitlerinin engellenmesi regression testleriyle korunacak.

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
