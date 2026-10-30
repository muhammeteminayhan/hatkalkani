---
name: geo-data-sources
description: HatKalkanı veri kaynakları. Erişim yolları, lisanslar, boyut uyarıları ve indirme tarifleri (Meta/WRI ağaç yüksekliği, Sentinel-2, Copernicus DEM, ESA WorldCover, OSM/Overpass, Overture binalar, Open-Meteo, NASA FIRMS). Veri keşfi veya indirme yapan alt ajanlara önceden yüklenir.
user-invocable: false
---

# Veri kaynakları ve erişim tarifleri

Etiketler:
- **[D]** 30 Ekim 2026'da resmi sayfadan doğrulandı.
- **[K]** İlk kullanımda doğrula ve docs/DATA_SOURCES.md'yi güncelle.

## Genel kurallar
- **Önce AOI:** AOI sınırını ve hat koridorunu üret; tüm verileri bunlara göre KIRP. Ülke veya il ölçeğinde indirme yapma.
- **COG pencere okuma:** Bulut-optimize dosyalarda tüm dosyayı indirme. rasterio ile HTTP üzerinden pencere oku (`/vsicurl/https://...` veya `s3://...` + ortam değişkeni `AWS_NO_SIGN_REQUEST=YES`).
- **Kayıt:** Her indirmeyi data/raw/MANIFEST.csv'ye kaydet. Lisansı ve atıf metnini docs/DATA_SOURCES.md'ye yaz.

## 1. Ağaç yüksekliği: Meta & WRI Canopy Height Maps
- **v1 [D]:**
  - Konum: `s3://dataforgood-fb-data/forests/v1/alsgedi_global_v6_float/`. Anonim erişim; AWS hesabı gerekmez.
  - Karo dizini: `tiles.geojson`. `tile` alanı quadkey; gözlem tarihi bilgisi de var.
  - Karo dosyası: `chm/<tile>.tif`.
  - HTTPS: `https://dataforgood-fb-data.s3.amazonaws.com/forests/v1/alsgedi_global_v6_float/chm/<tile>.tif`
- **v2 [K]:**
  - Konum: `s3://dataforgood-fb-data/forests/v2/global/dinov3_global_chm_v2_ml3/` (DINOv3 ile iyileştirilmiş sürüm).
  - Yapıyı `aws s3 ls --no-sign-request` veya `s3fs.S3FileSystem(anon=True)` ile keşfet.
  - Source Cooperative'de GeoParquet karo dizini ve STAC ile yeniden paketlenmiş bir kopyası var (`tge-labs/meta-chm-v2`).
  - v2'ye erişim 30 dakikada çözülemezse v1'i kullan ve bunu DECISIONS.md'ye yaz.
- **Lisans:** CC BY 4.0, ticari kullanım serbest.
- **Atıf:** "Meta and World Resources Institute (WRI) - 2024. High Resolution Canopy Height Maps (CHM). Source imagery for CHM © 2016 Maxar."
- **Doğruluk:** Çözünürlük ~1 m; v1'in ortalama mutlak hatası ~2,8 m.
- **Tarih:** Görüntü tarihi karodan karoya değişir; çoğunlukla birkaç yıl öncesidir. Bu veriyi "taban çizgisi" olarak kullan ve güncel durumu Sentinel-2 ile destekle.
- **UYARI:** Karolar çok büyüktür. Yalnızca hat koridoru tamponunun (ör. ±30 m) pencerelerini oku ve parça parça işle.

## 2. Sentinel-2 L2A: Element 84 Earth Search STAC [D]
- **Erişim:** STAC API `https://earth-search.aws.element84.com/v1`. Koleksiyon `sentinel-2-c1-l2a`, yoksa `sentinel-2-l2a` [K: ilk sorguda doğrula].
- **Bantlar:** red (B04), nir (B08), nir08 (B8A), swir16 (B11) ve scl (sahne sınıfı).
  - NDVI = (B08 − B04) / (B08 + B04)
  - NDMI = (B8A − B11) / (B8A + B11)
- **Yükleme:** pystac-client ile ara, odc-stac ile AOI'ye kırpılmış küp yükle.
- **Bulut maskesi:** SCL sınıfları 3, 8, 9 ve 10'u maskele, ardından dönem medyanını al.
- **Dönemler:** config/aoi.yaml → `periods`. Geriye dönük test için as_of öncesi bahar dönemi; güncel demo için son 45 gün.
- **Atıf:** "Contains modified Copernicus Sentinel data <yıl>".

## 3. Yükseklik: Copernicus DEM GLO-30 [D]
- **Erişim:** Earth Search koleksiyonu `cop-dem-glo-30` veya anonim `s3://copernicus-dem-30m/`.
- **Türevler:** eğim (°), bakı ve TPI.
- **Atıf:** Copernicus DEM'in resmi atıf metni [K].

## 4. Arazi örtüsü: ESA WorldCover 10 m [D]
- **Erişim:** Anonim `s3://esa-worldcover/v200/2021/map/`. Karolar 3°×3°'tür [K: dosya adı kalıbını listeleyerek doğrula].
- **Sınıflar:** 10 ağaç, 20 çalılık, 30 otlak, 40 tarım, 50 yapı, 60 çıplak, 80 su.
- **Lisans:** CC BY 4.0.
- **Atıf:** "© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium".

## 5. Elektrik hatları: OpenStreetMap
- **Overpass API:** `https://overpass-api.de/api/interpreter`. Yoğunsa alternatif bir Overpass sunucusu kullan [K].
- **Etiketler:**
  - `power=line`: iletim
  - `power=minor_line`: dağıtım / orta gerilim
  - `power=cable`: yer altı; risk dışı
  - `power=tower|pole`: direk
  - `voltage`: volt cinsinden; `;` ile birden çok değer olabilir.
- **Önce say, sonra çek:** Önce `out count;` ile say, sonra geometrileri `out geom;` ile al. İlçe alanı için `area["name"="<ilçe>"]["admin_level"="6"]` kullan; aynı adda başka yer olmadığını il sınırıyla doğrula.
- **Toplu alternatif:** Geofabrik Türkiye çıkarımı (`https://download.geofabrik.de/europe/turkey-latest.osm.pbf`). Büyüktür; yalnızca Overpass yetmezse kullan.
- **Lisans:** ODbL 1.0. **Atıf:** "© OpenStreetMap contributors".

## 6. İdari sınırlar
- OSM idari sınırları (ilçe = `admin_level=6`) Overpass ile alınır.
- Yedek: geoBoundaries TUR ADM2 [K].

## 7. Binalar (yerleşim arayüzü ve etkilenen yapı vekili)
- **Overture Maps buildings [K]:**
  - Konum: `s3://overturemaps-us-west-2/release/<release>/theme=buildings/type=building/*` (anonim).
  - Önce son release adını listele.
  - DuckDB ile bbox filtresiyle oku: `httpfs` ve `spatial` eklentileri, `s3_region='us-west-2'`.
- **Yedek:** OSM `building=*` (Overpass, küçük bbox).
- **Lisans:** Kaynağa göre ODbL veya CDLA. Release notlarından doğrula [K].

## 8. Hava: Open-Meteo [K: parametre adlarını ilk çağrıda doğrula]
- **Uç noktalar:**
  - Geçmiş: `https://archive-api.open-meteo.com/v1/archive`
  - Tahmin: `https://api.open-meteo.com/v1/forecast`
  - Anahtar gerekmez.
- **Saatlik değişkenler:** `wind_speed_10m`, `wind_gusts_10m`, `wind_direction_10m`, `relative_humidity_2m`, `temperature_2m`.
- **Örnekleme:** AOI'yi ~10 km'lik ızgarayla örnekle. Birden çok koordinatı tek istekte gönderebilirsin. Yanıtları önbelleğe al.
- **Kullanım şartı:** Ücretsiz API ticari olmayan kullanım içindir; ürünleşmede ücretli plan gerekir (PITCH notu).
- **Lisans:** CC BY 4.0. **Atıf:** "Weather data by Open-Meteo.com".

## 9. Aktif yangın noktaları: NASA FIRMS [D]
- **API:** `https://firms.modaps.eosdis.nasa.gov/api/area/csv/<MAP_KEY>/<SOURCE>/<batı,güney,doğu,kuzey>/<GÜN 1-10>/<YYYY-MM-DD>`
- **SOURCE:**
  - Arşiv: `VIIRS_SNPP_SP`, `VIIRS_NOAA20_SP`, `MODIS_SP`
  - Yakın gerçek zamanlı: `*_NRT`
- **Gün aralığı:** Tek istekte en fazla 10 gün; tarihleri 10'ar günlük dilimlerle döngüle.
- **Sınır:** 10 dakikada 5000 işlem. Hangi tarihlerin mevcut olduğunu `/api/data_availability/` gösterir.
- **Anahtar:** MAP_KEY, `FIRMS_MAP_KEY` ortam değişkeninden (.env) okunur. Yoksa DUR ve KULLANICIDAN GEREKEN yaz.
- **Not:** FIRMS ateş PİKSELİ verir (VIIRS ~375 m). Bu, tutuşma noktası değildir.
- **Atıf:** NASA FIRMS'in önerdiği atıf metni [K].

## 10. Belgelenmiş vakalar ve mevzuat (web)
- **Haberler:** Hat kaynaklı yangın haberlerini yalnızca "medya kaynaklı" etiketiyle kaydet: tarih, il/ilçe, yaklaşık konum, kaynak URL ve haberdeki dayanak (itfaiye raporu, valilik açıklaması vb.).
- **Yönetmelik:** Elektrik Kuvvetli Akım Tesisleri Yönetmeliği (RG 30.11.2000/24246; mevzuat.gov.tr). Ağaçlara yatay ve düşey mesafe tablolarını docs/REGULATION_NOTES.md'ye "DOĞRULANMADI" etiketiyle aktar. Değerleri bir insan doğrular.
