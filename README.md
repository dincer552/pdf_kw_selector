# 2026-09-11 — EBM-Papst ayrı görünüm ve motor karşılaştırma kuralı

### Bugün eklenen işler

- [x] **PDF1'de `EBM-Papst` belge seviyesinde tespit ediliyor:** `Model Brand = EBM-Papst` ifadesi PDF1'in tüm sayfalarında aranıyor; yalnızca Rated Power sayfalarına bağlı değil.
- [x] **EBM-Papst PDF1 AHU/Project eşleşmesinden çıkarılmıyor:** PDF2 ile Project → AHU eşleşmesi normal şekilde devam ediyor.
- [x] **EBM-Papst için motor kW karşılaştırması yapılmıyor:** EBM-Papst tespit edilen PDF1/AHU için motor karşılaştırması atlanıyor; normal AHU eşleşmesi korunuyor.
- [x] **EBM-PAPST sekmesi eklendi:** EBM tespit edilen PDF1 dosyası, proje, AHU, EBM bulunan sayfalar, eşleşen PDF2 dosyaları ve durum bilgisi ayrı sekmede gösteriliyor.

---

# 2026-09-11 — PDF1 Rated Power ve fiziksel motor adedi keşfi

### Bugün eklenen işler

- [x] **PDF1 motor gücü `Rated Power` alanından okunuyor:** Sabit `Rated Power [kW]` etiketi bulunuyor ve hemen karşısındaki değer esas alınıyor. Örneğin `Rated Power [kW] 7,500 x (1x1)` → **7.5 kW**.
- [x] **Rated Power grup bilgisi fiziksel motor adedini belirliyor:** `1x1` → 1 fiziksel motor, `2x1` → 2 fiziksel motor. İlk sayı motor adedidir; ikinci sayı grup bilgisidir.
- [x] **PDF text extraction satır kırılmaları destekleniyor:** `Rated Power [kW]` ve değer aynı satırda veya extraction nedeniyle ayrılmış olsa da eşleştiriliyor.
- [x] **Motor karşılaştırmasına fiziksel motor kayıtları gönderiliyor:** Rated Power değeri ve `NxM` grubu birlikte korunarak PDF2 tarafıyla motor bazında eşleştiriliyor.

---

# 2026-09-11 — PDF1 Project/Unit Reference keşfi sabit alanlara bağlandı

### Bugün eklenen işler

- [x] **PDF1 ekipman keşfi artık yalnızca `Unit Reference` alanının karşısındaki değeri kullanıyor:** Ekipman tipi (`AHU`, `FAHU`, `HKS` vb.) değişken kabul ediliyor; `Unit Reference` etiketi sabit referans olarak kullanılıyor. `AHU-KIT`, `AHUKIT` ve sayfa içinde geçen diğer tesadüfi AHU/HKS ifadeleri PDF1 ekipman keşfine dahil edilmiyor.
- [x] **PDF1 Project keşfi artık `Project` alanının karşısındaki değeri kullanıyor:** PDF1'de proje adı sabit `Project` etiketi üzerinden alınıyor. PDF2'deki proje adı farklı/uzun yazılmış olsa bile mevcut normalize + eşleştirme mantığıyla karşılaştırılmaya devam ediyor.
- [x] **PDF1'de eski genel AHU/HKS metin taraması kaldırıldı:** `Unit Reference` değeri bulunamazsa dosya adından ekipman tahmini de PDF1 için yapılmıyor.
- [x] **`Unit Reference` ve `Project` için PDF text extraction varyasyonları desteklendi:** Etiket ve değer aynı satırda veya ayrı satırlarda gelse de değer alınabiliyor.

---

# 2026-09-11 — Project/AHU eşleşme rezervasyon hatası düzeltildi

### Bugün eklenen düzeltme

- [x] **Project → AHU eşleşmesinin kaybolmasına neden olan rezervasyon bug'ı düzeltildi:** Aday eşleşmeler final seçiminden önce `used` olarak işaretleniyordu; bu nedenle gerçek eşleşmeler son aşamada elenip `project_matches=[]` ve `ahu_matches=[]` oluşabiliyordu. Rezervasyon artık yalnızca final eşleşme seçildiğinde yapılıyor.
- [x] **EŞLEŞMEYEN PDF'LER sekmesi gerçek eşleşme sonucunu kullanacak şekilde doğrulandı:** Eşleşen AHU PDF'leri sahipsiz listesine düşmeyecek; gerçekten eşleşmeyen PDF'ler listede kalacak.

---

# 2026-09-11 — Canlı eşleşme teşhisi ve sahipsiz PDF görünümü

### Bugün eklenen işler

- [x] **Canlı Project → AHU eşleşme teşhis logları:** Master scan sonrası PDF1/PDF2 proje grupları, normalize adlar, AHU kümeleri, AHU overlap adayları, proje skor/status/reason bilgileri ve elenen/final eşleşmeler ayrıntılı olarak loglanıyor.
- [x] **AHU eşleşme teşhis logları:** Her proje grubunda PDF1/PDF2 AHU listeleri, eşleşme adayı, skor, durum, neden ve eşleşmeye giren PDF yolları loglanıyor. Böylece gerçek PDF çalışmasında `project_matches=[]` / `ahu_matches=[]` nedeninin hangi aşamada oluştuğu görülebilecek.
- [x] **EŞLEŞMEYEN PDF'LER sekmesi:** Sonuç ekranına ayrı bir sekme eklendi. AHU eşleşmesine giremeyen PDF'ler PDF1/PDF2 tarafı, dosya adı, proje, tespit edilen AHU ve neden bilgisiyle listeleniyor; sekme başlığında toplam sayı gösteriliyor.
- [x] **Sahipsiz PDF teşhisi:** Bir PDF'nin hiçbir başarılı AHU eşleşmesine girmemesi görünür hale getirildi ve bu liste işlem loguna da yazılıyor.

---

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
