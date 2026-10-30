# Veri kaynakları kataloğu

data-scout ve data-engineer günceller. Erişim tarifleri `.claude/skills/geo-data-sources/SKILL.md` dosyasındadır.

Durum: ⬜ kontrol edilmedi · 🔎 erişim doğrulandı · ✅ indirildi/işlendi · ⚠️ sorunlu · 🙋 kullanıcı gerekli

| # | Veri | Amaç | Erişim | Lisans | Durum | Yerel yol | Not |
|---|---|---|---|---|---|---|---|
| 1 | OSM elektrik hatları ve direkler | Hat geometrisi | Overpass API | ODbL 1.0 | ⬜ (2026-10-30: Overpass 502, 2 deneme; docs/reports/F1-2-erisim.md) | data/raw/osm/ | Dağıtım hattı kapsaması ilçeye göre değişir |
| 2 | Meta/WRI ağaç yüksekliği (v2, yoksa v1) | Ağaç–hat yakınlığı | S3 anonim, COG pencere okuma | CC BY 4.0 | 🔎 [D 2026-10-30] v1 tiles.geojson HTTP 200; v2 chm/ listelendi (tiles.geojson 58.9 MB, indirilmedi). İzmir v1 karo: 30 (data/interim/f1_chm_tiles_izmir.csv) | data/raw/chm/ | 1 m; MAE ~2,8 m (v1); taban yılı karoya göre |
| 3 | Sentinel-2 L2A | Kuruluk (NDMI), NDVI | Earth Search STAC | Copernicus açık veri | 🔎 [D 2026-10-30] https://earth-search.aws.element84.com/v1; sentinel-2-c1-l2a (İzmir 2025-04-01..05-31 matched=407) | data/raw/s2/ | Koleksiyon adı doğrulanacak |
| 4 | Copernicus DEM GLO-30 | Eğim, TPI | Earth Search veya S3 | Copernicus DEM lisansı | 🔎 [D 2026-10-30] STAC cop-dem-glo-30; S3 N37–N39 × E026–E027 HEAD 200 | data/raw/dem/ | |
| 5 | ESA WorldCover 2021 | Yakıt sürekliliği | S3 anonim | CC BY 4.0 | 🔎 [D 2026-10-30] İzmir: N36E024, N36E027, N39E024, N39E027 (HEAD 200) | data/raw/worldcover/ | |
| 6 | Overture binalar (yedek: OSM) | Yerleşime yakınlık, etkilenen bina vekili | S3 + DuckDB | ODbL (docs.overturemaps.org/attribution, 15 May 2026) | 🔎 [D 2026-10-30] release 2026-10-21.0 | data/raw/buildings/ | Son release keşfedilecek |
| 7 | İdari sınırlar | AOI | OSM (yedek: geoBoundaries) | ODbL / CC BY | ⬜ | data/raw/boundaries/ | |
| 8 | Open-Meteo saatlik hava | Rüzgâr hamlesi, nem | API, anahtarsız | CC BY 4.0; ücretsiz API ticari olmayan kullanım içindir | 🔎 [D 2026-10-30] archive-api HTTP 200; 2015-01-01 erişilebilir | data/raw/weather/ | |
| 9 | NASA FIRMS | Yangın noktaları (geriye dönük test, geçmiş yoğunluk) | API (MAP_KEY) | NASA açık veri | 🙋 .env anahtar kontrolü izin kuralıyla engellendi (2026-10-30); docs/reports/F1-2-erisim.md | data/raw/firms/ | Anahtar .env'de olmalı |
| 10 | Haber vakaları | Vaka incelemesi | Web | — | ⬜ | docs/reports/F1-3-vakalar.md | Medya kaynaklı, doğrulanmadı |
| 11 | Kuvvetli Akım Yönetmeliği | Açıklık mesafeleri | mevzuat.gov.tr | Kamu | ⬜ | data/manual/regulation/ | İnsan doğrular |
| 12 | (İsteğe bağlı) EDAŞ hat GIS verisi | Gerçek şebeke | Şirketten | Sözleşmeye göre | 🙋 | data/manual/edas/ | Pilot görüşmelerinden |

## Sürüm, koleksiyon ve erişim tarihi (F2, DOC-F2)
Kaynak: `data/raw/MANIFEST.csv` ve `data/interim/izmir_menderes/*_meta.json`.

| # | Veri | Sürüm / koleksiyon | Erişim tarihi | Kayıt kaynağı |
|---|---|---|---|---|
| 1 | OSM hat ve ilçe sınırı | Overpass API; sürüm/zaman damgası [DOĞRULANMADI] | 2026-10-30 | MANIFEST: osm_boundary, osm_power_lines |
| 2 | Meta/WRI CHM | v2 `dinov3_global_chm_v2_ml3`; 4 karo (1221003102, 1221003103, 1221003120, 1221003121); v1 yalnızca referans | 2026-10-30 | MANIFEST: chm_v2_corridor_window; chm_meta.json |
| 3 | Sentinel-2 L2A | `sentinel-2-c1-l2a`; backtest 2025-04-15..2025-05-31 (24 sahne), güncel 2026-09-15..2026-10-30 (21 sahne) | 2026-10-30 | MANIFEST: sentinel-2 satırları; s2_meta.json |
| 4 | Copernicus DEM GLO-30 | `cop-dem-glo-30`; sürüm [DOĞRULANMADI] | 2026-10-30 | MANIFEST: DEM satırları |
| 5 | ESA WorldCover | v200, 2021 | 2026-10-30 | MANIFEST: WorldCover satırı |
| 6 | Overture binalar | release 2026-10-21.0 | 2026-10-30 | MANIFEST: overture-buildings; buildings_meta.json |
| 7 | Open-Meteo arşiv | archive-api; sürüm yok; 2022–2025 yaz pencereleri | 2026-10-30 | MANIFEST: open-meteo satırları |
| 8 | NASA FIRMS | VIIRS_SNPP_SP, VIIRS_NOAA20_SP, MODIS_SP; yıllar 2015–2025 | 2026-10-30 | MANIFEST: firms satırları |

Risk: MANIFEST'teki FIRMS URL'lerinde MAP_KEY `***` ve kaynak `VIIRS_SNPP_SP|NRT` gösterimi var; tarih parametresi kısaltılmış görünüyor. [DOĞRULANMADI]

## F2-1 notu (ingest)
- OSM hat ve ilçe sınırı (Overpass, overpass-api.de; kumi.systems yedek, erişilemedi): ODbL 1.0. Ham yanıtlar `data/raw/izmir_menderes/`, kayıtlar `data/raw/MANIFEST.csv`. Çıktılar `data/processed/izmir_menderes/{boundary,lines,segments}.parquet`.
- EDAŞ dosyası (GPKG/SHP) `data/manual/edas/` altına konursa OSM yerine kullanılır; beklenen sütunlar: kimlik (id/hat_id/objectid), gerilim (kV ya da V; sütun adı gerilim/voltage/kv), çizgi geometri, tanımlı CRS.
