# Kaynaklar ve atıflar

Şartname, kullanılan verinin, açık kaynak yazılımın, görsellerin ve üçüncü taraf içeriğin kaynağının belirtilmesini istiyor. Bu dosyayı doc-writer güncel tutar; arayüz altbilgisi `/api/meta/sources` üzerinden aynı listeyi gösterir.

## Veri
| Veri | Lisans | Atıf metni | URL |
|---|---|---|---|
| OpenStreetMap (elektrik hatları, ilçe sınırı, yedek bina) | ODbL 1.0 | © OpenStreetMap contributors | https://www.openstreetmap.org/copyright |
| Meta & WRI Canopy Height Maps v2 (`dinov3_global_chm_v2_ml3`); v1 yedek | CC BY 4.0 | Meta and World Resources Institute (WRI) - 2024. High Resolution Canopy Height Maps (CHM). [v1 metninde ek: Source imagery for CHM © 2016 Maxar. v2 için Maxar ibaresi: DOĞRULANMADI (ATTR-1b, 31 Eki 2026: v2 kaynaklarında bulunamadı)] | https://registry.opendata.aws/dataforgood-fb-forests/ ; https://dataforgood-fb-data.s3.amazonaws.com/forests/v2/global/dinov3_global_chm_v2_ml3/ |
| Copernicus Sentinel-2 L2A (Earth Search `sentinel-2-c1-l2a`) | Copernicus Sentinel veri şartları (ücretsiz, açık) | Contains modified Copernicus Sentinel data 2025, 2026 | https://earth-search.aws.element84.com/v1 |
| Copernicus DEM GLO-30 (Earth Search `cop-dem-glo-30`) | Copernicus DEM lisansı; ücretsiz kullanım, atıfla ("free use with attribution") | "© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved". DOĞRULANDI (ATTR-1b, 31 Eki 2026; lisans PDF'iyle birebir karşılaştırılmadı). Kayıt ibaresi: "ESA/Copernicus" | https://dataspace.copernicus.eu/node/1306 ; https://earth-search.aws.element84.com/v1/collections/cop-dem-glo-30 |
| ESA WorldCover 2021 v200 | CC BY 4.0 | © ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium | https://esa-worldcover.org |
| Overture Maps buildings, release 2026-10-21.0 | ODbL-1.0 (kayıt bazında `sources[].license`; Menderes çıkarımında hem Microsoft ML Buildings hem OpenStreetMap kayıtları ODbL-1.0) | Overture Maps Foundation (buildings theme; sources incl. OpenStreetMap contributors, Microsoft, Google, Esri) | https://docs.overturemaps.org/attribution ; https://overturemaps.org |
| Open-Meteo (arşiv API) | CC BY 4.0; ücretsiz API yalnızca ticari olmayan kullanım için | Weather data by Open-Meteo.com | https://open-meteo.com ; https://archive-api.open-meteo.com/v1/archive |
| NASA FIRMS (VIIRS_SNPP_SP, VIIRS_NOAA20_SP, MODIS_SP) | NASA açık veri | NASA FIRMS open data; cite: NASA FIRMS (LANCE/EOSDIS) | https://firms.modaps.eosdis.nasa.gov |

## Veri notları
- **Overture (AOI, `data/interim/izmir_menderes/buildings_meta.json`):** Kayıt sayısı 65 873; Microsoft ML Buildings 57 475, OpenStreetMap 8 398. Bu AOI çıktısında Google ve Esri kaydı görünmüyor; atıf metni yine de bu kaynakları anıyor. Lisans kayıt bazında ham veriden okunur: ODbL-1.0 (paylaşım-benzeri yükümlülük geçerli).
- **CHM v2:** Görüntü tarihi ayak izi başına `metadata/<karo>.geojson` → `acq_date` alanında var (bkz. `chm_acq_segment.parquet`); `chm_meta.json`'daki "unknown" ifadesi eskidir. Tarihler 2016-2020; güncel durum için Sentinel-2 ile destekle.
- **Open-Meteo:** Ücretli plan, ürünleşmede gerekir (PITCH notu).
- **[DOĞRULANMADI]:** CHM v2 için Maxar satırı.

## Yazılım
| Bileşen | Lisans |
|---|---|
| MapLibre GL JS 4.7.1 (web/vendor/, lisans: web/vendor/LICENSE-maplibre-gl.txt) | BSD-3-Clause |
| Python kütüphaneleri | F5'te `uv pip list` çıktısından lisanslarıyla eklenecek |

## Harita altlığı
- **Çevrimiçi altlık:** OpenFreeMap "positron" stili (https://tiles.openfreemap.org/styles/positron). API anahtarı ve kayıt gerekmez. Sitesindeki SSS (2026-10-31 kontrol): ticari kullanım serbest; atıf zorunlu. Stil kodu MIT, OpenMapTiles şeması CC BY 4.0, veri ODbL (OpenStreetMap).
- **Atıf metni:** "OpenFreeMap © OpenMapTiles Data from OpenStreetMap" (MapLibre atıf denetimi) ve altbilgide "Altlık: OpenFreeMap © OpenMapTiles, veri © OpenStreetMap katkıcıları".
- **Çevrimdışı yedek:** Ağ yoksa (4 sn zaman aşımı) düz arka plan, /api/aoi/boundary ilçe sınırı ve hat katmanları gösterilir; altbilgi bunu belirtir.
- **Not:** Şartlar sunucu tarafında değişebilir; jüri demosundan önce yeniden bakın.

## Yapay zekâ araçları
Bu projede kod, analiz ve metin üretiminde Claude Code (Anthropic) kullanıldı. Üretilen içeriğin doğruluğu takım tarafından kontrol edildi.
