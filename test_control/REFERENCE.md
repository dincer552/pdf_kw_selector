# TEST KONTROL — FAZ 0 REFERANS ENVANTERİ

Bu dosya, Python migrasyonundan önce `dincer552/umut-test-pro` içindeki C# uygulamasının referans davranışını dondurur.

## Referans kaynak

- Repository: `dincer552/umut-test-pro`
- Uygulama: `TestKontrolProg`
- Ana veri modeli: `TestKontrolProg/Datas.cs`

## Ana veri modeli

`Datas.cs` içinde aşağıdaki gruplar bulunuyor:

- `ProjectInfo`: Project / AHU / üçüncü proje bilgisi
- Fan: `FanTip`, Supply/Return fan sayısı, Supply/Return airflow, debi/basınç kontrol durumları
- Filtre: 18 elemanlı `Filtreler`
- Sensör: 11 ayrı sensör sözlüğü
- Modül: Rotor, RunAround, ChangeOver, DX, Nemlendirici, vanalar, elektrikli ısıtıcı, komponentler, Room BMS, TempAvgEn
- `SensorVar`: sensör var/yok bilgileri
- Damper: 6 damper için `DamperDatas`
- `Not`: not listesi
- User: `UserName` ve imaj byte verisi
- PDF rapor yolları: `pdfPath`, `newPdfPath`

Referans kaynak: `TestKontrolProg/Datas.cs`. fileciteturn249file0

## Ana ekran — Form1

`Form1` aşağıdaki alt ekranları açıyor:

- Fan Kontrol
- Damper Kontrol
- Filtre Kontrol
- Modüller
- Sensörler
- User

Ayrıca ana proje bilgilerini `Datas.ProjectInfo` içine aktarır; notları `Datas.Not` içine aktarır ve Excel/PDF raporlarını çağırır. Kontrol tamamlandığında ilgili ana ekran etiketi `Kontrol Edildi` durumuna alınır. Referans kaynak: `TestKontrolProg/Form1.cs`. fileciteturn253file0

## Fan Kontrol

- Fan tipi: 1 = Danfoss Ziehl-Abegg, 2 = EC Ziehl-Abegg, 3 = EC EBM-Papst
- Supply fan sayısı
- Return fan sayısı
- Supply airflow
- Return airflow
- Debi kontrolü
- Basınç kontrolü
- Kaydet sonrası ana formda Fan Kontrol tamamlandı durumu

Geçersiz/boş sayısal girişler C# tarafında `0` yapılır. Referans: `TestKontrolProg/FanKontrol.cs`. fileciteturn254file0

## Damper Kontrol

6 damper alanı bulunur. Her alanın damper sayısı kaydedilir:

1. Fresh
2. Supply
3. Return
4. Exhaust
5. Mix
6. Bypass

Boş/geçersiz giriş `0` olarak ele alınır. Referans: `TestKontrolProg/DamperKontrol.cs`. fileciteturn255file0

## Filtre Kontrol

18 filtre seçimi `Datas.Filtreler` içine `1/0` ve filtre adı olarak kaydedilir. Referans: `TestKontrolProg/FiltreKontrol.cs`. fileciteturn256file0

## Modüller

Referans kodda Rotor, RunAround, Room BMS, TempAvgEn, ChangeOver, DX, Nemlendirici, 4 vana, 7 komponent, elektrikli ısıtıcı ve 3x3 elektriksel veri alanı işlenir.

DX kademe değeri 0–5 aralığına, nemlendirici kademe değeri 0–8 aralığına sınırlandırılır. Referans: `TestKontrolProg/Moduller.cs`. fileciteturn257file0

## Sensörler

11 sensör grubu modelde tutulur. Mevcut C# sürümünde `Verileri Çek` butonu C600/SCOPE üzerinden `SUPPLY_AIR_TEMP` okur ve Supply Air sıcaklığı alanına yazar. Manuel `Kaydet` tüm 11 sensör grubunu veri modeline aktarır. Referans: `TestKontrolProg/Sensorler.cs`. fileciteturn258file0

## User

User ekranı PNG kullanıcı görsellerini `user` klasöründe tutar; kullanıcı adı ve varsayılan görsel ayarlarını uygulama ayarlarında saklar. User ekleme, silme ve seçim davranışı mevcut C# kodunda bulunur. Referans: `TestKontrolProg/UserControl.cs`. fileciteturn259file0

## Raporlama

Excel raporlamada mevcut şablon `Test_Report_BACnet_Modbus.xlsx` kullanılır. Proje, fan, modül, damper, filtre, sensör, elektrikli ısıtıcı ve not alanları rapora aktarılır. Referans: `TestKontrolProg/helperFuncs.cs`. fileciteturn260file0

PDF rapor üretimi C# tarafında ayrıca `helperFuncs2` üzerinden yürütülür.

## Faz 0 sonucu

C# uygulamasının ana veri modeli ve taşınacak ana ekran/modül fonksiyonları referans olarak belirlendi. Python tarafında davranış korunacak; C# referans alınarak aşamalı doğrulama yapılacak.
