# F1-2 Erişim raporu (veri kaynakları)

Tarih: 2026-10-30. Model: claude-haiku-5-5. Kanıt yöntemi: HTTP HEAD, S3 liste (XML), STAC POST (context.matched), küçük metadata. Raster indirilmedi.

## 1. Kaynak durumu (7 doğrulama maddesi)

| # | Kaynak | Durum | Kanıt |
|---|---|---|---|
| 1 | Meta/WRI CHM v1 | erişildi | `https://dataforgood-fb-data.s3.amazonaws.com/forests/v1/alsgedi_global_v6_float/tiles.geojson` HTTP 200, 15.2 MB, 56 145 karo. chm/ ve metadata/ listelendi. |
| 1 | Meta/WRI CHM v2 | erişildi (kısmi) | `.../forests/v2/global/dinov3_global_chm_v2_ml3/` listelendi; chm/ ve metadata/ var. `tiles.geojson` 58.86 MB, 50 MB sınırını aştığı için indirilmedi. |
| 2 | Sentinel-2 L2A | erişildi | `https://earth-search.aws.element84.com/v1`. Koleksiyon `sentinel-2-c1-l2a` ve `sentinel-2-l2a` ikisi de var. İzmir bbox [26.0,37.0,28.6,39.6], 2025-04-01/2025-05-31: c1-l2a matched=407, l2a matched=389. |
| 3 | Copernicus DEM GLO-30 | erişildi | STAC `cop-dem-glo-30` (lisans alanı: proprietary). S3 HEAD 200: `copernicus-dem-30m/Copernicus_DSM_COG_10_N37_00_E026_00_DEM/...DEM.tif`; N38/N39 × E026/E027 için de 200. |
| 4 | ESA WorldCover v200 2021 | erişildi | S3 liste `esa-worldcover.s3.eu-central-1.amazonaws.com/?prefix=v200/2021/map/`. İzmir için HEAD 200: `ESA_WorldCover_10m_2021_v200_N36E024_Map.tif`, `N36E027`, `N39E024`, `N39E027`. |
| 5 | Overture Maps | erişildi | Son release `2026-10-21.0` (önceki: 2026-09-23.0/.1). Buildings: `overturemaps-us-west-2/release/2026-10-21.0/theme=buildings/type=building/part-*.zstd.parquet`. Lisans: docs.overturemaps.org/attribution (sayfa tarihi 15 May 2026): buildings için ODbL. |
| 6 | Open-Meteo archive | erişildi | `https://archive-api.open-meteo.com/v1/archive` HTTP 200. Parametreler: `wind_speed_10m`, `wind_gusts_10m`, `wind_direction_10m`, `relative_humidity_2m`, `temperature_2m` (birimler km/h, °, %, °C). 2015-01-01 HTTP 200. |
| 7 | NASA FIRMS | belirsiz | Anahtarlı istek yapılmadı. Bkz. bölüm 3. |

## 2. Aday ilçe × kaynak kapsamı

| İlçe | CHM v1/v2 | S2 (2025 Nis–May) | DEM | WorldCover | Overture | Open-Meteo |
|---|---|---|---|---|---|---|
| Menderes | İzmir karoları var; ilçe–karo eşlemesi YAPILAMADI | İzmir bbox sahneleri var (ilçe bbox'ı ayrı sorgulanmadı) | İzmir karoları | N36E024/E027, N39E024/E027 | release 2026-10-21.0 | erişildi (İzmir içi koordinat) |
| Çeşme | aynı | aynı | aynı | aynı | aynı | aynı |
| Ödemiş | aynı | aynı | aynı | aynı | aynı | aynı |

İlçe sınırı alınamadı. Overpass `rel[admin_level=6]` sorgusu iki denemede (ilk, 60 s bekleyip ikinci deneme) HTTP 502 döndü. geoBoundaries TUR ADM2 GeoJSON'un (GitHub 302) boyutu doğrulanmadı. Bu yüzden her aday için karo kimliği ve tarih çıkarılamadı.

## 3. FIRMS anahtar durumu

- `.env` mevcut (içerik okunmadı).
- `grep -c '^FIRMS_MAP_KEY=.' .env` ve koordinatörün istediği maskeli `mapkey_status` komutu, izin sistemindeki deny kuralı nedeniyle engellendi ("grep from .env was blocked by a deny rule"). Anahtarın boş mu dolu mu olduğu doğrulanamadı. Kural aşılmaya çalışılmadı.
- FIRMS dokümantasyon sayfası `https://firms.modaps.eosdis.nasa.gov/api/` HTTP 200 (anahtarsız).

## 4. CHM karo bulguları (İzmir)

- v1: bbox (26.0–28.7E, 37.0–39.7N) ile 30 karo kesişti. Kimlikler quadkey olarak doğrulandı (quadkey bbox ile polygon bbox: 0 uyumsuzluk). 30 karonun 30'u için chm/ HEAD 200.
- v2: aynı 30 v1 karosunun alt karoları, 113 kimlik (10 haneli quadkey).
- Görüntü tarihi: karo geojson'unda tarih alanı yok (yalnızca `tile`). Tarih, `metadata/<tile>.geojson` içindeki `acq_date` özniteliğinden alınır. 6 v1 karosu için dağılım çıkarıldı (ör. 122100300: 2019-03-29 ×2, 2019-06-10, 2019-09-21, 2019-10-02). 9 v1 karosu 20 MB'ı aştı ve atlandı. v2 metadata indirilmedi.
- CSV: `data/interim/f1_chm_tiles_izmir.csv` (143 satır: 30 v1 + 113 v2; sütunlar tile_id, surum, s3_key, acq_date, not).

## 5. Sınır ihlali ve geri alma

- Arka plan metadata indirmesi, 20 MB sınırını aşan dosyaları (en büyüğü 57 MB) indirdi. Bunlar silindi; yarım kalan dosyalar da silindi. Kalan: `data/raw/_scout/meta_v1/` (6 dosya, 44 MB; hepsi ≤20 MB).
- `data/raw/MANIFEST.csv` kaydı yapılmadı (scout kapsamı dışında).

## 6. Skill güncellemesi

- Meta v2 `tiles.geojson` 58.9 MB: 50 MB sınırıyla indirilemez. Skill'e "v2 karo indeksi için chm/ listeleme, tiles.geojson yerine" notu eklenmeli.
- Meta v1 `CHM_acquisition_date.tif` 2.0 GB. Tarih için karo başına `metadata/<tile>.geojson` (`acq_date`) kullanılmalı. Skill'deki "gözlem tarihi bilgisi var" ifadesi netleştirilmeli.
- Overture release adı tarih bazlı (`YYYY-MM-DD.N`). Skill'e "son release 2026-10-21.0" ve listeleme komutu eklenmeli.
- Sentinel-2: `sentinel-2-c1-l2a` mevcut; `[K]` kapatılabilir.
- Copernicus DEM: Earth Search `cop-dem-glo-30` ve S3 HEAD doğrulandı.
- WorldCover dosya kalıbı: `ESA_WorldCover_10m_2021_v200_<N##E###>_Map.tif`, 3° karo.
- Open-Meteo parametre adları doğrulandı; birimler km/h.

## 7. Açık maddeler

- FIRMS anahtar doğrulaması. KULLANICIDAN GEREKEN: `.env` içindeki `FIRMS_MAP_KEY` boş mu dolu mu; kontrol için izin kuralının bu okumaya izin vermesi ya da kullanıcı onayı gerekli.
- Aday ilçe sınırları (Overpass 502). Kaynak tekrar denenmeli ya da geoBoundaries ADM2 dosya boyutu HEAD ile kontrol edilmeli.
- v1 9 büyük ve v2 tüm metadata dosyaları için tarih.
