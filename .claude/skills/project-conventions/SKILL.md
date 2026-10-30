---
name: project-conventions
description: HatKalkanı kod ve veri kuralları. Teknoloji yığını, klasörler, koordinat sistemleri, dosya biçimleri, test, platform uyumu ve çıktı hijyeni. Kod veya veri işi yapan alt ajanlara önceden yüklenir.
user-invocable: false
---

# HatKalkanı proje kuralları

## Proje bağlamı
HatKalkanı, elektrik dağıtım hatlarından kaynaklanan orman yangını riskini 100 m'lik hat parçası düzeyinde puanlar. Üç çıktısı vardır:
- risk haritası,
- budama/drone iş emri listesi,
- rüzgârlı gün için hedefli önleyici kesinti senaryosu.

Pilot bölge İzmir'de bir ilçedir (config/aoi.yaml → `selected`). Hedef COP31 Creathon demosu: dizüstünde, çevrimdışı çalışan bir harita uygulaması.

## Teknoloji yığını
- **Python ve uv:** Python 3.12 ve uv kullanılır.
  - Bağımlılık eklemek: `uv add <paket>` (gerekçeyi rapora yaz).
  - Çalıştırmak: `uv run ...`
- **Coğrafi:** geopandas (pyogrio motoru), shapely 2, pyproj, rasterio, rioxarray, xarray, pystac-client, odc-stac.
- **Tablo:** pandas, pyarrow, duckdb.
- **API:** FastAPI ve uvicorn.
- **Test ve lint:** pytest ile ruff.
- **Web:** web/ altında derleme adımı olmayan tek sayfa (index.html, app.js, style.css) ve MapLibre GL JS.

## Klasörler
- `data/raw/<kaynak>/`: indirilen ham dosyalar. Her indirme `data/raw/MANIFEST.csv`'ye yazılır: kaynak, url, yerel_yol, bayt, sha256, tarih, lisans.
- `data/interim/<aoi>/`: ara ürünler. Loglar `data/interim/logs/` altına.
- `data/processed/<aoi>/`: API'nin okuduğu nihai ürünler.
- `data/manual/`: kullanıcının elle koyduğu dosyalar. Salt-okunur kabul et.
- `config/`: tüm eşik, ağırlık ve tarihler buradadır. Sabit sayıları koda gömme.

## Koordinat sistemleri
- **Depolama ve API:** EPSG:4326 (lon/lat).
- **Mesafe, alan ve tampon hesapları:** config/aoi.yaml → `metric_crs` (İzmir için EPSG:32635, UTM 35N).
- **Açık dönüşüm:** Raster ve vektörü birleştirirken CRS'yi açıkça dönüştür; asla varsayma. Fonksiyonlar girdinin CRS'sini kontrol etsin.

## Dosya biçimleri
- **Vektör:** GeoParquet birincil biçimdir. Dışa aktarım GeoJSON, GPKG ve CSV'dir.
- **Raster:** Cloud Optimized GeoTIFF (deflate sıkıştırma, döşemeli).
- **Kimlikler:** Kararlı ve okunabilir olsun (ör. `segment_id = "<osm_way_id>_<0001>"`).

## Kod kuralları
- **Dil:** Kod, tanımlayıcılar ve yorumlar İngilizce; doküman, rapor ve arayüz metni Türkçe.
- **Yapı:** Saf hesap fonksiyonları ile dosya ve ağ işlemleri ayrı katmanlarda olsun. Tip ipuçları kullan.
- **Testler:** Her modülün tests/ altında küçük sentetik veriyle bir testi olsun. Ağ gerektiren testler `@pytest.mark.network` ile işaretlenir ve varsayılan çalıştırmada atlanır.
- **Platform:** Windows ve macOS'ta çalışmalı. Yollar için pathlib kullan, kabuk betiği yerine Python betiği yaz, dosyaları `encoding="utf-8"` ile aç.
- **Ağ çağrıları:**
  - zaman aşımı,
  - 3 kez üstel beklemeli yeniden deneme,
  - önbellek (aynı dosya ikinci kez indirilmez),
  - MANIFEST kaydı.
- **Bellek:** Tek işlemde 4 GB'ı aşma. Büyük rasterleri pencere pencere oku; asla tüm karoyu belleğe alma.
- **Gizli bilgi:** Anahtarları yalnızca ortam değişkeninden oku (python-dotenv ile .env). .env'i asla okuma, yazdırma veya commit etme.

## Çıktı hijyeni (bağlamı korumak için)
- Uzun komut çıktısını dosyaya yönlendir (`> data/interim/logs/<ad>.log 2>&1`) ve yalnızca son ~20 satırına bak.
- DataFrame'in tamamını yazdırma; `head()`, `shape`, sayımlar ve `describe()` yeter.
- İş bitince sonucu tek satırla özetle.

## Lisans ve atıf
Yeni bir veri kaynağı veya kütüphane eklediğinde docs/DATA_SOURCES.md ve docs/ATTRIBUTIONS.md'ye satır ekle: ad, lisans, atıf metni ve URL.
