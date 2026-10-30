# F1-1 — Aday ilçelerde OSM elektrik hattı kapsamı

Model: claude-haiku-5-5 (Haiku 5.5)
Tarih: 2026-10-30
OSM veri tarihi (timestamp_osm_base): 2026-10-30T17:07:05Z ile 2026-10-30T17:18:16Z arası (her sorgunun yanıtındaki değer; ayrıntı için bkz. Ham yanıt tablosu)

## 1. Doğrulama (admin_level=6, İzmir)

Her ilçe için `area["admin_level"="6"]["name"=...]` sorgusu tek alan döndürdü. Hepsinde `network=TR35-districts` (İzmir, TR35) etiketi var.

| İlçe | OSM relation id | wikidata |
|---|---|---|
| Menderes | 269196 (area 3601269196) | Q2996335 |
| Çeşme | 268454 (area 3601268454) | Q217720 |
| Ödemiş | 823318 (area 3601823318) | Q293927 |
| Seferihisar (ek) | 269195 (area 3601269195) | Q2523774 |
| Torbalı (ek) | 269519 (area 3601269519) | Q1011344 |

## 2. Karşılaştırma tablosu

Uzunluklar `length()` ile `sum` alınarak Overpass üzerinde hesaplandı. Kesirler yalnızca "voltage" etiketi olan way'lerin uzunluğunun toplam uzunluğa oranıdır.

| İlçe | power=line km (way) | line voltage oranı (uzunluk; way) | minor_line km (way) | minor voltage oranı | Kule (tower) | Direk (pole) | Yüzölçümü km² | Toplam hat km (line+minor) | ~100 m segment (×10) | Kule / km² |
|---|---|---|---|---|---|---|---|---|---|---|
| Menderes | 204,41 (16) | 74,5% (8) | 0,42 (1) | 0% (0 of 1) | 287 | 5 | 777 | 204,83 | 2048 | 0,37 |
| Çeşme | 179,03 (23) | 70,4% (11) | 0,00 (0) | — | 341 | 11 | 285 | 179,03 | 1790 | 1,20 |
| Ödemiş | 142,61 (16) | 48,6% (2) | 1,67 (5) | 63,3% (4) | 423 | 0 | 1019 | 144,28 | 1443 | 0,42 |
| Seferihisar (ek) | 83,92 (4) | 40,5% (1) | 0,32 (3) | 0% (0 of 3) | 114 | 12 | 375 | 84,24 | 842 | 0,30 |
| Torbalı (ek) | 323,93 (18) | 88,1% (9) | 16,00 (9) | 83,2% (2) | 438 | 31 | 577 | 339,93 | 3399 | 0,76 |

Yüzölçümü kaynakları (tr.wikipedia, ilçe maddesinde "Yüzölçümü ... km²dir" cümlesi; bilgi kutusu ile uyumlu):
- Menderes 777 km²: https://tr.wikipedia.org/wiki/Menderes,_İzmir
- Çeşme 285 km²: https://tr.wikipedia.org/wiki/Çeşme,_İzmir (HGM'ye atıf)
- Ödemiş 1019 km²: https://tr.wikipedia.org/wiki/Ödemiş
- Seferihisar 375 km²: https://tr.wikipedia.org/wiki/Seferihisar
- Torbalı 577 km²: https://tr.wikipedia.org/wiki/Torbalı

Not: Yüzölçümü ikincil kaynaktan (Vikipedi) alındı; resmî değer için TÜİK/HGM teyidi önerilir. Kule/km² ve segment sayıları bu değerlere dayanır.

## 3. Ek aday gerekçesi (medya kaynaklı, doğrulanmadı)

Bu bölüm yalnızca haber özetlerine dayanır; hat kaynaklı iddialar resmî rapor değildir.
- **Seferihisar:** Haziran sonu 2025 yangını Menderes'ten başlayıp Seferihisar'a yayıldı; Gediz Elektrik ve elektrik hattı tartışması haber konusu. Kaynaklar: https://haber.sol.org.tr/haber/raporda-yeniden-duzenleme-izmir-itfaiyesine-gore-yanginin-sebebi-gediz-degilmis-400760 ; https://www.aljazeera.com/news/2025/6/30/firefighters-in-turkiye-battle-to-contain-wildfires-that-threaten ; https://www.thenationalnews.com/news/mena/2025/07/01/rescuers-battle-izmir-wildfires-as-strong-winds-cause-blazes-to-spread-in-pictures
- **Torbalı:** Ahmetli mahallesinde yangın haberi var (uçak/helikopter müdahalesi); hektar bilgisi ve hat bağlantısı bulunamadı. Gerekçesi zayıf; ikinci ek aday olarak önerilmez.
- **Menderes (config):** Valilik açıklaması ve ilk itfaiye raporu hat kaynaklı; sonradan değiştirildiği haberi var: https://www.gzt.com/gundem/izmir-valisinden-aciklama-yanginin-elektrik-hattindan-kaynakli-ciktigini-dusunuyoruz-3799293 ; https://haber.sol.org.tr/haber/raporda-yeniden-duzenleme-izmir-itfaiyesine-gore-yanginin-sebebi-gediz-degilmis-400760
- **Ödemiş/Çeşme:** 2025 Temmuz yangınları ve tahliyeler: https://medyascope.tv/2025/07/03/cesme-ve-odemiste-orman-yanginlari-suruyor-bazi-mahalleler-tahliye-edildi/ ; Ödemiş için hat kaynaklı itfaiye raporu iddiası: https://haber.sol.org.tr/haber/itfaiye-raporu-sirketi-yalanladi-odemiste-3-kisinin-olumune-sebep-olan-yanginin-sorumlusu-gdz

Yangın geçmişi ve orman örtüsü bu görevin kapsamı dışındadır; yukarıdakiler yalnızca aday seçimi için bağlamdır.

## 4. Sorgu metni (aday başına; ilçe adı değiştirilerek)

```
[out:json][timeout:300];
area["boundary"="administrative"]["admin_level"="6"]["name"="Menderes"]->.a;
way["power"="line"](area.a); make s k="line",n=count(ways),len_m=sum(length()); out;
way["power"="line"]["voltage"](area.a); make s k="line_v",n=count(ways),len_m=sum(length()); out;
way["power"="minor_line"](area.a); make s k="minor",n=count(ways),len_m=sum(length()); out;
way["power"="minor_line"]["voltage"](area.a); make s k="minor_v",n=count(ways),len_m=sum(length()); out;
node["power"="tower"](area.a); make s k="tower",n=count(nodes); out;
node["power"="pole"](area.a); make s k="pole",n=count(nodes); out;
```

Doğrulama sorgusu: `[out:json][timeout:90]; area["admin_level"="6"]["name"~"^(Menderes|Çeşme|Ödemiş)$"]["boundary"="administrative"]; out tags;` (ek adaylar için Seferihisar|Torbalı).

`length()` hata vermedi; uzunluklar Overpass tarafında hesaplandı.

## 5. Ham yanıt ve sorgu dosyaları

Dizin: `C:\Users\merto\Desktop\hatkalkani\data\interim\f1_overpass\`
- Sorgular: `q_menderes.ql`, `q_cesme.ql`, `q_odemis.ql`, `q_seferihisar.ql`, `q_torbali.ql`, `q_verify_menderes.ql`, `q_verify_all3.ql`, `q_verify_extra.ql`
- Ham yanıtlar: `raw_menderes.json`, `raw_cesme.json`, `raw_odemis.json`, `raw_seferihisar.json`, `raw_torbali.json`
- Doğrulama yanıtları: `verify_menderes.json`, `verify_all3.json`, `verify_extra.json`

Sunucu notu: overpass-api.de sık 502 (kapasite) döndürdü; her sorgu için 30 sn beklenip yeniden denendi. overpass.kumi.systems bu oturumda zaman aşımına uğradı (sonuç alınamadı); tüm ölçümler overpass-api.de üzerinden alındı.

## 6. Sınırlar

- **Sınır taşan hatlar:** `way(area)` tek bir way'in sınırın dışına uzanan kısmını da içerir; `length()` hattın tamamını sayar. Bu nedenle uzunluklar, özellikle küçük ilçelerde, ilçe içindeki gerçek uzunluğun üstündedir. Kırpma yapılmadı (Overpass dışı hesap bu görevin kapsamı dışında).
- **Yalnızca OSM etiketi:** Kapsam, OSM'deki mevcut etiketlemeye bağlıdır; güncel olmayan veya eksik etiketler ölçümü etkiler. Özellikle Seferihisar ve Çeşme'de minor_line etiketi yoktur.
- **Küçük örneklem:** Menderes minor_line yalnızca 1 way (0,42 km) içerir; bu oran anlamlı değildir.
- **Yüzölçümü:** Vikipedi kaynaklı; resmî kaynak teyidi bekliyor.

## 7. Öneri (yalnızca OSM veri kalitesi)

OSM verisine göre Menderes, config'deki diğer adaylarla karşılaştırıldığında dengeli bir seçimdir: 204 km power=line hattı, hat uzunluğunun %74,5'i voltaj etiketli ve yaklaşık 2048 segment, işlenebilir bir hacimde. Çeşme (kule yoğunluğu 1,20/km², %70,4 voltaj) ve Torbalı (340 km, %88 voltaj etiketi) OSM kalitesi bakımından da güçlüdür; ancak Torbalı 3399 segmentle işlem yükünü artırır ve Ödemiş'in hat voltaj etiketi (%48,6) zayıftır. Bu nedenle OSM kalitesine göre önerilen aday Menderes'tir; Çeşme ikinci sıradadır. Yangın geçmişi ve orman örtüsü bu öneriye dahil edilmemiştir.
