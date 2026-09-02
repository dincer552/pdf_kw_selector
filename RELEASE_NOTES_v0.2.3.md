# PDF kW Selector v0.2.3

## CI düzeltmeleri

Bu sürüm v0.2.2 sonrası kalan 5 pytest hatasını giderir.

- Semantik fan motoru alanları Türkçe/İngilizce alias ve Unicode normalization ile eşleştirilir.
- `Fan Motor: 3 kW` artık `Unit Total Power: 4 kW` ve `Total Heating` gibi aggregate değerlerden doğru şekilde ayrılır.
- Database motor sırası `Vant` sonra `Asp` olacak şekilde deterministiktir.
- Page discovery marker'ı `explicit rated power` olarak standardize edildi.
- Motor grup bilgisi `1x1/2x1/3x1` string olarak korunur; fiziksel motor sayısı bu grup bilgisinden türetilir.
- `Return air` desteği `Aspiratör` olarak açıkça korunur.

## Build

Windows workflow testler geçtiğinde `PDF_KW_Selector_v0.2.3.exe` üretir ve `PDF_KW_Selector_v0.2.3_Windows` artifact'ını yükler.
