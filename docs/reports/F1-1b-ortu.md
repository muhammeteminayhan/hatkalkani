# F1-1b: Ağaç ve çalı örtüsü (ESA WorldCover 2021)

Veri: ESA WorldCover v200, **2021 tarihli** 10 m arazi örtüsü. Betik: `notebooks/f1_candidate_stats.py`.

## Tablo 1: İzmir ilçeleri (30 ilçe)

| İlçe | Alan km² | Ağaç % | Çalı % | Ağaç+çalı % |
|---|---:|---:|---:|---:|
| Narlıdere | 44.8 | 78.54 | 2.36 | 80.9 |
| Selçuk | 351.79 | 63.71 | 11.85 | 75.56 |
| Kemalpaşa | 643.59 | 72.75 | 2.46 | 75.21 |
| Karaburun | 409.78 | 45.34 | 29.65 | 74.99 |
| Urla | 675.48 | 58.42 | 16.46 | 74.89 |
| Buca | 205.2 | 65.53 | 6.33 | 71.85 |
| Bayındır | 556.78 | 63.98 | 2.61 | 66.59 |
| Güzelbahçe | 82.66 | 57.33 | 8.47 | 65.81 |
| Karabağlar | 98.65 | 57.95 | 6.08 | 64.03 |
| Seferihisar | 386.18 | 52.73 | 10.92 | 63.64 |
| Bornova | 229.63 | 57.91 | 5.55 | 63.45 |
| Menderes | 787.24 | 53.52 | 8.98 | 62.5 |
| Beydağ | 171.11 | 56.0 | 1.25 | 57.25 |
| Kınık | 494.35 | 52.07 | 2.83 | 54.9 |
| Bergama | 1540.92 | 47.87 | 4.97 | 52.83 |
| Gaziemir | 62.7 | 47.91 | 3.36 | 51.27 |
| Tire | 764.66 | 46.19 | 3.34 | 49.53 |
| Karşıyaka | 51.25 | 42.16 | 7.33 | 49.49 |
| Ödemiş | 1014.95 | 47.89 | 1.41 | 49.3 |
| Torbalı | 551.69 | 43.4 | 4.99 | 48.39 |
| Dikili | 546.86 | 37.53 | 8.12 | 45.66 |
| Balçova | 21.38 | 38.02 | 7.07 | 45.09 |
| Kiraz | 552.37 | 41.4 | 1.72 | 43.12 |
| Foça | 245.92 | 25.94 | 15.54 | 41.47 |
| Çeşme | 273.56 | 14.57 | 20.37 | 34.95 |
| Aliağa | 387.7 | 25.63 | 6.32 | 31.95 |
| Menemen | 587.09 | 25.14 | 4.6 | 29.74 |
| Bayraklı | 34.16 | 22.52 | 6.81 | 29.33 |
| Çiğli | 131.98 | 9.03 | 2.01 | 11.04 |
| Konak | 24.39 | 10.29 | 0.47 | 10.77 |

## Tablo 2: Aday ilçelerde hat koridoru (±30 m)

| İlçe | line km | minor_line km | Toplam km | >=154 kV | 33-36 kV | Diğer | Etiketsiz | Koridor ağaç+çalı % | (line) | (minor) | İlçe geneli % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Menderes | 92.01 | 0.43 | 92.44 | 60.99 | 0.0 | 0.0 | 31.45 | 52.57 | 52.79 | 10.71 | 62.5 |
| Çeşme | 98.23 | 0.0 | 98.23 | 45.1 | 0.0 | 0.0 | 53.14 | 24.84 | 24.84 | - | 34.95 |
| Ödemiş | 104.65 | 1.67 | 106.31 | 38.88 | 0.0 | 1.06 | 66.38 | 24.26 | 23.81 | 52.85 | 49.3 |
| Seferihisar | 42.84 | 0.17 | 43.01 | 10.18 | 0.0 | 0.0 | 32.83 | 82.67 | 83.1 | 0.0 | 63.64 |
| Torbalı | 154.4 | 6.74 | 161.14 | 116.56 | 4.05 | 0.0 | 40.54 | 47.24 | 49.03 | 7.36 | 48.39 |

Gerilim sütunları kırpılmış hat km'sidir; `voltage` etiketindeki (`;` ile çoklu ise en yüksek) değere göre sınıflanır.

## CHM karo eşlemesi (F1-2 eksiği)

`data/interim/f1_chm_tiles_izmir.csv` karoları (quadkey sınırları) ilçe poligonlarıyla kesiştirildi; sonuç `candidate_corridors.csv` içinde `chm_tiles` ve `chm_dates` sütunlarında.

| İlçe | Karo sayısı | Görüntü tarihi aralığı |
|---|---:|---|
| Menderes | 7 | 2016-07-22..2020-02-19 (v1 tarihli: 2; v2 karolarda tarih yok) |
| Çeşme | 6 | 2018-09-17..2020-03-01 (v1 tarihli: 2; v2 karolarda tarih yok) |
| Ödemiş | 9 | 2016-07-06..2020-02-18 (v1 tarihli: 1; tarihsiz v1 (butce): 122101200/122100313/122101202; v2 karolarda tarih yok) |
| Seferihisar | 4 | 2019-03-04..2020-02-16 (v1 tarihli: 2; v2 karolarda tarih yok) |
| Torbalı | 8 | 2019-09-11..2020-02-18 (v1 tarihli: 3; tarihsiz v1 (butce): 122100313; v2 karolarda tarih yok) |

Tarih bulgusu:
- Tarihler yalnızca v1 karoları için vardır (CSV'de ya da `metadata/<karo>.geojson` içindeki `acq_date` poligonlarından; poligonlar ilçe sınırıyla kırpılarak). v2 (10 haneli quadkey) karolarında tarih bilgisi yoktur.
- Görüntü tarihleri 2016-2020 arasındadır; yani CHM taban çizgisi 5-9 yaşındadır (Çeşme, Seferihisar, Torbalı çoğunlukla 2018-2020).
- 200 MB indirme sınırı nedeniyle 122101200, 122101202 (Ödemiş) ve 122100313 (Ödemiş, Torbalı) v1 karolarının metadata'sı indirilmedi (toplam 167 MB indirildi); Ödemiş ve Torbalı aralıkları bu yüzden kısmidir. Bu karolar sonra gerekirse indirilebilir (sırasıyla 49, 55, 63 MB).

## Yöntem
- İlçe sınırları: OSM `admin_level=6` ilişkileri (İzmir il alanı içinde), Overpass `out geom`. Alan EPSG:32635'te hesaplandı.
- Yüzdeler: WorldCover COG'undan yalnızca ilçe bbox penceresi okundu (tüm karo değil); poligon maskesiyle sınıf 10 (ağaç) ve 20 (çalı) sayıldı; satırlar enleme göre cos(lat) ile ağırlıklandı. Payda ilçe poligonunun tüm pikselleridir (su ve yapı dahil).
- Hatlar: OSM `power=line` ve `power=minor_line` (bbox sorgusu), ilçe poligonuyla kırpıldı, EPSG:32635'te uzunluk ölçüldü. Koridor = hat tamponu (±30 m, `config/aoi.yaml`), ilçeyle kesişimi, aynı yöntemle sayıldı.
- Önbellek: `data/interim/f1_candidates/cache/`.

## Sınırlamalar
- WorldCover 2021 tarihlidir; 2021 sonrası yangın, kesim ve yeni yerleşim yansımaz.
- 10 m piksel ve 60 m'lik koridor: koridor yaklaşık 6 piksel genişliğindedir, karışık pikseller ve kenar etkisi belirgindir. Ağaç sınıfı Akdeniz maki, zeytin ve çam arasında ayrım yapmaz; kentsel ilçelerde (ör. Narlıdere %78) ağaç payı yüksek çıkabilir, sınıflandırma hatası olasıdır.
- OSM hat verisi eksik olabilir. Etiketsiz (voltage yok) hat payı yüksektir (%30-60); line ile minor_line ayrımı OSM etiketine bağlıdır, minor_line km'leri çok düşük olduğundan minor koridor yüzdeleri istatistiksel olarak zayıftır.
- Overpass: kumi.systems sunucusuna bu ağdan ulaşılamadı, overpass-api.de kullanıldı (ilk denemelerde HTTP hataları, yeniden deneme çalıştı).
- Kullanıcı etiketlemesi dışında bir doğrulama yapılmadı; ilçe alanları OSM sınırından gelir, resmi yüzölçümüyle küçük farklar olabilir.
- Kaynak ve atıf: © ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium (CC BY 4.0); © OpenStreetMap contributors (ODbL). docs/DATA_SOURCES.md bu görevde değiştirilmedi; satırların eklenmesi orkestratöre bırakıldı.
