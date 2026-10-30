# Veri kaynakları kataloğu

data-scout ve data-engineer günceller. Erişim tarifleri `.claude/skills/geo-data-sources/SKILL.md` dosyasındadır.

Durum: ⬜ kontrol edilmedi · 🔎 erişim doğrulandı · ✅ indirildi/işlendi · ⚠️ sorunlu · 🙋 kullanıcı gerekli

| # | Veri | Amaç | Erişim | Lisans | Durum | Yerel yol | Not |
|---|---|---|---|---|---|---|---|
| 1 | OSM elektrik hatları ve direkler | Hat geometrisi | Overpass API | ODbL 1.0 | ⬜ | data/raw/osm/ | Dağıtım hattı kapsaması ilçeye göre değişir |
| 2 | Meta/WRI ağaç yüksekliği (v2, yoksa v1) | Ağaç–hat yakınlığı | S3 anonim, COG pencere okuma | CC BY 4.0 | ⬜ | data/raw/chm/ | 1 m; MAE ~2,8 m (v1); taban yılı karoya göre |
| 3 | Sentinel-2 L2A | Kuruluk (NDMI), NDVI | Earth Search STAC | Copernicus açık veri | ⬜ | data/raw/s2/ | Koleksiyon adı doğrulanacak |
| 4 | Copernicus DEM GLO-30 | Eğim, TPI | Earth Search veya S3 | Copernicus DEM lisansı | ⬜ | data/raw/dem/ | |
| 5 | ESA WorldCover 2021 | Yakıt sürekliliği | S3 anonim | CC BY 4.0 | ⬜ | data/raw/worldcover/ | |
| 6 | Overture binalar (yedek: OSM) | Yerleşime yakınlık, etkilenen bina vekili | S3 + DuckDB | Kaynağa göre ODbL/CDLA | ⬜ | data/raw/buildings/ | Son release keşfedilecek |
| 7 | İdari sınırlar | AOI | OSM (yedek: geoBoundaries) | ODbL / CC BY | ⬜ | data/raw/boundaries/ | |
| 8 | Open-Meteo saatlik hava | Rüzgâr hamlesi, nem | API, anahtarsız | CC BY 4.0; ücretsiz API ticari olmayan kullanım içindir | ⬜ | data/raw/weather/ | |
| 9 | NASA FIRMS | Yangın noktaları (geriye dönük test, geçmiş yoğunluk) | API (MAP_KEY) | NASA açık veri | 🙋 | data/raw/firms/ | Anahtar .env'de olmalı |
| 10 | Haber vakaları | Vaka incelemesi | Web | — | ⬜ | docs/reports/F1-3-vakalar.md | Medya kaynaklı, doğrulanmadı |
| 11 | Kuvvetli Akım Yönetmeliği | Açıklık mesafeleri | mevzuat.gov.tr | Kamu | ⬜ | data/manual/regulation/ | İnsan doğrular |
| 12 | (İsteğe bağlı) EDAŞ hat GIS verisi | Gerçek şebeke | Şirketten | Sözleşmeye göre | 🙋 | data/manual/edas/ | Pilot görüşmelerinden |
