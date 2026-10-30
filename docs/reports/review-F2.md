# REV-F2: Faz 2 veri hattı, kod ve yöntem incelemesi

- **Model:** claude-opus-5-5 (Opus 5.5), code-reviewer
- **Tarih:** 2026-10-31
- **Kapsam:**
  - `git diff 3b786fc -- src scripts tests config`: common, boundary, lines, segments, test_ingest ve `config/aoi.yaml` içindeki `current_asof`.
  - İzlenmeyen dosyalar: sentinel2, dem, worldcover, rasters, chm, buildings, firms, weather, `scripts/run_pipeline.py` ve 5 test dosyası.
  - Üretilmiş çıktılar salt okunur incelendi: `data/processed/izmir_menderes/`, `data/interim/izmir_menderes/`, `data/raw/MANIFEST.csv`, `data/interim/logs/`.
- **Sınırlar:** Ağ kullanılmadı, veri indirilmedi, `.env` okunmadı. Kod dosyası değiştirilmedi.

## Yapılan kontroller
| Komut / kontrol | Sonuç |
|---|---|
| `uv run pytest` | 48 geçti, 2 ağ testi seçilmedi, 1 DeprecationWarning (chm.py:423) |
| `uv run ruff check src scripts tests` | All checks passed |
| Vektör çıktıları (salt okunur betik, `.venv` python `-I`) | boundary, lines, segments, chm_segment_stats, buildings, firms, wind: şema, CRS, uzunluk ve sayımlar |
| Raster çıktıları | S2, DEM, WorldCover ve CHM: dtype, nodata, ızgara, değer dağılımı, koridor kapsaması |
| Gizli bilgi taraması | Değer okunmadan yalnız sayım yapıldı. MANIFEST, 22 log dosyası, interim `*.json`, `docs/`, `src/`, `tests/`, `config/` ve `.claude/agent-memory/` tarandı; 32 haneli hex belirteç sayısı 0 |

## Genel değerlendirme
Veri hattı sağlam kurulmuş:
- Saf hesap ile G/Ç katmanları ayrı.
- CRS dönüşümleri açıkça yapılıyor.
- CHM yalnız koridor pencerelerinden okunuyor (≈8 MB).
- MANIFEST, sha256 önbelleği ve pipeline doğrulaması çalışıyor. Önbellekten tüm ingest 28,5 sn sürüyor.
- STATUS'taki sayıların hepsi veriden yeniden üretildi; yalnız lisans beyanı veriyle çelişiyor.

**Kritik bulgu yok.** Üç Yüksek bulgu var:
- İki önbellek anahtarı eksik. Bunlar sessizce bayat ya da yanlış veri üretebilir.
- Overture lisansı yanlış beyan edilmiş.

Orta bulguların çoğu ileriye dönük riskler: F3'te zaman sızıntısına açık dosya düzeni, EDAŞ girişinde Türkçe sütun adı sorunu, Overpass hata yanıtı ve sessiz OSM yedeği.

## Kritik ve Yüksek bulgular (commit öncesi düzeltilecekler)

**Kritik:** yok.

### Y1. CHM istatistik önbelleği model parametrelerini kapsamıyor
- **Yer:**
  - `src/hatkalkani/ingest/chm.py:495-502`: `cache_key`
  - `chm.py:522-525`: önbellek isabetinde erken dönüş
  - `chm.py:73-84`: `load_params`
- **Sorun:**
  - Anahtar yalnız şu alanları içeriyor: segments sha256, `half_width_m`, `metric_crs`, `out_res_m`, `version`.
  - Oysa `chm_segment_stats.parquet` şu parametrelere de bağlı: `clearance_band_m`, `min_encroach_canopy_m`, `strike_margin_m`, `strike_max_distance_m`, `strike_min_cluster_px`.
  - Bant genişlikleri bilerek yer tutucu (`placeholder_unverified: true`). REGULATION_NOTES doğrulanınca ya da F3 kalibrasyonunda değiştirildiklerinde ingest "cache hit" verir. vegetation_encroachment ve strike_trees eski parametrelerle kalır; hata ya da uyarı çıkmaz.
  - `placeholder_unverified` bayrağı ne `chm_meta.json`'a ne istatistik dosyasına taşınıyor.
- **Düzeltme:**
  - Raster önbelleğini ve istatistik önbelleğini ayır. İstatistik anahtarına `dataclasses.asdict(params)` ekle; ya da istatistikleri her koşuda yerel tif'ten yeniden hesapla (birkaç saniye sürer).
  - `placeholder_unverified` değerini meta'ya ve parquet metadata'sına yaz.
  - Parametre değişince yeniden hesaplandığını sınayan bir test ekle.

### Y2. FIRMS ham önbelleği AOI'ye, bbox'a ve tarih penceresine bağlı değil
- **Yer:**
  - `src/hatkalkani/ingest/firms.py:184-185`: `year_file`
  - `firms.py:197` ve `:240`: `is_cached`
  - `firms.py:229-231`: bbox ve son tarih
- **Sorun:** Ham dosya yolu `data/raw/firms/{source}_{year}.csv`. Önbellek anahtarı yalnız kaynak ve yıldan oluşuyor.
  - (a) Başka bir AOI Menderes bbox'ıyla indirilmiş dosyaları sessizce kullanır. `config/aoi.yaml`'da 5 aday var ve `--aoi` genel bir parametre. Sonuç: yanlış yangın geçmişi ve yanlış backtest olayları.
  - (b) `periods.backtest_season` sonu ya da `MARGIN_KM` değişirse 2025-09-30'da kesilmiş 2025 dosyası yenilenmez.
  - (c) NRT ile doldurulmuş bir yıl, SP verisi çıktığında güncellenmez.
- **Şu anki Menderes çıktısı doğru:** bbox 26,8865–27,3710 / 37,9350–38,3641, 3.180 satırın tamamı SP.
- **Düzeltme:**
  - Yolu `data/raw/firms/<aoi_id>/<source>_<year>.csv` yap. Yanına bbox, tarih aralığı ve kullanılan data_id'leri (SP/NRT) tutan bir json koy; okurken karşılaştır.
  - MANIFEST `url` alanına gerçek data_id'yi ve tarih aralığını yaz.

### Y3. Overture bina lisansı yanlış beyan ediliyor (CDLA-Permissive-2.0)
- **Yer:**
  - `src/hatkalkani/ingest/buildings.py:39-41` ve `:272`
  - `docs/ATTRIBUTIONS.md:13` ve `:18`
  - `buildings_meta.json` → `license`
  - MANIFEST'teki overture satırının `lisans` alanı
  - `docs/STATUS.md:44` ve `:65`
- **Sorun:**
  - Ham Overture çıkarımındaki kayıt bazlı `sources[1].license` alanı her iki veri kümesinde de **`ODbL-1.0`**. Bbox içi ham kayıtlar: Microsoft ML Buildings 78.888, OpenStreetMap 15.832.
  - "CDLA-Permissive-2.0 (Microsoft ML Buildings kaynaklı)" iddiası verinin kendisiyle çelişiyor. ODbL atıf ve paylaşım-benzeri (share-alike) yükümlülüğü getirir; CDLA-Permissive-2.0'da paylaşım-benzeri yükümlülük yoktur. Yani bu beyan yükümlülükleri olduğundan hafif gösteriyor.
  - Kod `license` sütununu okuyor (buildings.py:158) ama çıktıya taşımıyor (`keep_cols`, :245-249). Bu yüzden "per-record in sources" ifadesi çıktıda doğrulanamıyor.
- **Düzeltme:**
  - `OVERTURE_LICENSE = "ODbL 1.0 (Overture buildings; per-record sources[].license)"` yap.
  - `license` sütununu `buildings.parquet`'e taşı ve meta'ya `by_license` sayımı ekle.
  - ATTRIBUTIONS ve STATUS satırlarını "ODbL 1.0" olarak düzelt.

## Özel kontrol sonuçları
| # | Kontrol | Sonuç | Kanıt / not |
|---|---|---|---|
| 1 | CHM v2 değeri uint8 metre, 255 = veri yok | **KISMEN DOĞRULANDI** | Yerel kanıt tutarlı: çıktı uint8, değerler 0–32 (p50 0, p90 5, p99 17, p99,9 25), %68,7 sıfır. Koridorda 255 yok; 925 segmentte `chm_valid_frac` 1,0. Değerler desimetre olsaydı 25 m'lik çam 250 olarak görünürdü. 0 nodata olarak bildirilmemiş (sıfırlar geçerli sayılıyor). **Ancak:** kaynak başlığı ve birincil doküman bu incelemede okunamadı (ağ yasağı). Varsayımın tek dayanağı `.claude/agent-memory/data-engineer/chm_notes.md`. Kod dtype, nodata ve ölçeği çalışma anında doğrulamıyor → O1 |
| 2 | Yaklaşım bandı koda gömülü mü? | **GEÇTİ** (gömülü değil) | `chm.py:83` değeri `risk_weights.yaml → parameters.clearance_band_m`'den okuyor; sayılar yalnız testlerde sabit. Eksikler: `placeholder_unverified` hiçbir yerde okunmuyor, bant değerleri CHM önbellek anahtarında yok (Y1), bilinmeyen sınıfta sessizce `mv` varsayılıyor (D8) |
| 3 | FIRMS_MAP_KEY sızıntısı | **GEÇTİ** | MANIFEST'teki 33 FIRMS satırının 33'ü `/csv/***/`. Önbellek dosya adlarında anahtar yok (`{source}_{year}.csv`). Hata iletileri yalnız durum kodu ya da maskeli istisna içeriyor (`firms.py:139`, `:152`, `:155`). MANIFEST, loglar ve interim json'larda 32 hex belirteç: 0. Artık riskler (kesme sonrası maskeleme, urllib3 DEBUG) → D3 |
| 4 | Zaman damgaları ve km/h → m/s | **GEÇTİ** (bir tanım eksik) | FIRMS: `acq_date` + `acq_time`, `zfill(4)` ve `utc=True` ile UTC'ye çevriliyor. `acq_date` ile UTC tarih %100 eşleşiyor; yıl dosyalarında yıl dışı satır yok. Open-Meteo: `wind_speed_unit=kmh` açıkça isteniyor, değerler /3,6 ile m/s'ye çevriliyor. `timezone=Europe/Istanbul`; yerel ile UTC arası fark tüm satırlarda 10.800 sn; NaT yok. Eksik olan, gün sınırının UTC mi yerel mi olduğunun tanımı → O10 |
| 5 | CRS (depolama 4326, hesap 32635) | **GEÇTİ** | Depolama EPSG:4326 (boundary, lines, segments, buildings). Uzunluk, alan, kırpma, tampon ve koridorlar EPSG:32635'te hesaplanıyor; `is_projected` ve CRS-yok kontrolleri var. Yeniden hesaplanan uzunluk farkı <1e-8 m. Tüm rasterler 32635'te ve segmentleri tamponlarıyla birlikte kapsıyor. Zayıf noktalar → D7, D8 |
| 6 | Segmentasyon, SKILL §1 | **GEÇTİ** (OSM yolu) | line/minor_line alınıyor; cable ile location=underground/underwater dışarıda. Kırpma metrik CRS'de. Gerilim tablosu ve `voltage_source` §1 ile birebir. 100 m bölme; 50 m'den kısa kuyruk önceki parçaya ekleniyor. Kimlik biçimi `{way}_{i:04d}`. 925 segment, 58,3–142,2 m, toplam 92,436 km (hat toplamına eşit); kimlikler tekil. Riskler EDAŞ yolunda (O6) ve OSM'deki hatalı kV etiketlerinde (D9) |
| 7 | Önbellek anahtarları | **KALDI** (kısmen) | S2: pencere ve current_asof var; bbox, sürüm ve parametreler yok. CHM: raster için iyi, istatistik parametreleri yok (Y1). FIRMS: AOI, bbox ve pencere yok (Y2). DEM ve WorldCover: yalnız sha256. Overture: release var, bbox yok. Open-Meteo: lat, lon ve tarih var → D2 |
| 8 | Bellek | **GEÇTİ** | CHM: 256 px'lik 494 parçada yalnız koridor pencereleri; seyrek GTiff'ten COG'a geçiş; geçerli piksel sayımı blok blok. S2: dask 512×512×1. Tam diziler AOI boyutunda: S2 1980×1723, WorldCover 3959×3445 uint8, DEM 1321×1149. Tek açık nokta DuckDB bellek sınırı (D10) |
| 9 | Zaman sızıntısı ve backtest pencereleri | **KISMEN** | Tutarlı olanlar: S2 backtest penceresi 2025-04-15..05-31 (sahneler 04-16..05-31, as_of'tan sonra değil); rüzgâr klimatolojisi 2022–2024 yazları; WorldCover 2021. Riskler: FIRMS ve rüzgâr dosyaları backtest sonrası veriyi dönem etiketi olmadan aynı dosyada tutuyor; `firms_history` bitişi ile as_of arasında boşluk var (O3). CHM tarihi doğrulanmadı (O2). OSM ve Overture as_of'tan sonraki tarihli (D13) |

**İdempotentlik:**
- QA-F2'de 5 dosyanın sha256'sı koşudan önce ve sonra aynı çıktı. Kod okumasında önbellek isabetinde rastgelelik ya da zaman damgası yazılmadığı görüldü (meta'daki süre alanları yalnız yeniden hesapta yazılıyor).
- Tek istisna: EDAŞ dosyası her koşuda yeniden `register` ediliyor ve MANIFEST'in `tarih` alanı değişiyor (`lines.py:216-217`; D4).

## Orta bulgular

### O1. CHM v2 piksel anlamı çalışma anında doğrulanmıyor
- **Yer:**
  - `chm.py:375-388`: kaynak açılışı, `WarpedVRT(nodata=None, add_alpha=True)`
  - `chm.py:420-428`: uint8 `merged`, `merge_into`
  - `chm.py:565`: `value_semantics`
- **Sorun:**
  - Kaynağın dtype, nodata, scale/offset ve units değerleri kontrol edilmiyor.
  - Kaynak örneğin uint16 desimetre olsaydı, numpy ataması değerleri uint8'e sessizce sarardı (wrap).
  - `value_semantics` meta'da kanıtlanmış bir olgu gibi yazılıyor.
- **Düzeltme:**
  - Her kaynak için `s.dtypes == ("uint8",)`, `s.scales == (1.0,)` ve `s.offsets == (0.0,)` doğrula; değilse hata ver.
  - `s.nodata`, `s.units` ve `s.tags()` değerlerini `chm_meta.json`'a `source_profile` olarak yaz.
  - Birincil kaynakla doğrula (Meta/WRI v2 belgesi ya da Source Cooperative `tge-labs/meta-chm-v2` STAC `raster:bands`) ve ADR-008'e bağla.

### O2. "v2'de görüntü tarihi yok" iddiası doğrulanmamış; CHM sızıntı durumu belirsiz
- **Yer:** `chm.py:560-564`, `docs/DECISIONS.md:61`. Skill'de aynı ifade [DOĞRULANMADI] etiketli.
- **Sorun:**
  - F1-2 raporu (`docs/reports/F1-2-erisim.md:10`, `:38`) v2 klasöründe `metadata/` dizini olduğunu ve "v2 metadata indirilmedi" diye yazıyor. v1'de tarih `metadata/<tile>.geojson` dosyasındaki `acq_date` alanından okunuyor. Yani v2'de tarih "yok" değil, "bakılmadı".
  - Görüntü as_of'tan (2025-05-31) sonraysa CHM özellikleri sızıntılı olur.
  - Görüntü 2016–2020 arasındaysa (v1 referansı) CHM, 2019 yangını öncesini gösteriyor olabilir; 2019'da 957 FIRMS tespiti var. Bu durumda veri bayattır.
- **Düzeltme:**
  - 4 karo için `metadata/<qk>.geojson` dosyasının varlığını ve `acq_date` alanını kontrol et.
  - Tarih bulunursa karo başına tarih aralığını meta'ya yaz. Bulunmazsa ifadeyi "v2 metadata'sında tarih alanı bulunamadı" olarak düzelt.
  - MODEL_CARD'a sızıntı değerlendirmesini yaz.

### O3. Backtest ve sonrası verisi aynı dosyada, dönem etiketi yok
- **Yer:**
  - `firms.py:230-262`: 2015-01-01..2025-09-30 arası tek bir `firms.parquet`
  - `weather.py:57-62` ve `:131-135`: klimatoloji yazları ile 2025-06-27..30 senaryo günleri tek bir `wind_hourly.parquet`
- **Sorun:**
  - Spec §2'ye göre wind_exposure yalnız `wind_climatology_summers` yıllarından, fire_history yalnız as_of öncesinden hesaplanır. Dosyalarda `period` sütunu yok.
  - F3'te p95 doğrudan dosyadan alınırsa as_of sonrası en rüzgârlı gün (29 Haz 2025, 24,0 m/s) klimatolojiye girer. firms.parquet de 941 sezon tespiti içeriyor.
  - Config tutarsızlığı: `firms_history` 2024-12-31'de bitiyor, as_of ise 2025-05-31. Aradaki 41 tespit hiçbir pencereye girmiyor; spec ise "as_of'tan önceki tespitler" diyor.
  - Güncel harita (current_asof 2026-10-30) için FIRMS verisi 2025-09-30'da bitiyor.
- **Düzeltme:**
  - Her satıra `period` yaz (`history`, `pre_asof_gap`, `backtest_season`, `climatology`, `scenario`) ya da her dönem için ayrı dosya üret.
  - firms_history ile as_of'u hizalamak için bir ADR yaz.
  - F3'teki as_of sızıntı testi bu etikete dayansın.

### O4. Overpass `remark` alanı kontrol edilmiyor
- **Yer:** `common.py:144-152`
- **Sorun:**
  - Overpass, zaman aşımı ya da bellek hatasında HTTP 200 ile eksik `elements` ve bir `remark` alanı döndürür.
  - Kod bu yanıtı önbelleğe ve MANIFEST'e yazıyor; sonraki koşularda da yeniden indirmiyor. Sonuç: sınır ya da hat verisinde sessiz eksiklik.
  - Mevcut iki yanıtta `remark` yok (doğrulandı).
- **Düzeltme:**
  - `remark` "error" ya da "timed out" içeriyorsa `ValueError` fırlat; döngü yeniden dener.
  - `osm3s.timestamp_osm_base` değerini (2026-10-30T17:49:06Z) meta'ya yaz. Bu, DATA_SOURCES'taki "zaman damgası [DOĞRULANMADI]" boşluğunu kapatır.

### O5. Overture yolundaki her hata sessizce OSM yedeğine düşüyor
- **Yer:** `buildings.py:225-242`
- **Sorun:**
  - `except Exception` kod ve şema hatalarını da yutuyor (ör. `sources[1].license` alanının kalkması).
  - Kaynak sessizce değişir: bina sayısı yaklaşık 65 bin yerine yaklaşık 8 bin olur. wui_exposure ve senaryodaki "etkilenen yapı" metriği değişir. Tek iz meta'daki `note` alanı.
- **Düzeltme:**
  - Yedeğe yalnız ağ ve IO hatalarında geç.
  - Yedek kullanılırsa uyarı bas; `--allow-osm-fallback` bayrağı yoksa sıfırdan farklı çıkış kodu ver.

### O6. EDAŞ girişi: Türkçe büyük harfli sütun adları ve kimlik tekilliği
- **Yer:** `lines.py:161`, `:46-48`, `:170`; `segments.py:66-69`
- **Sorun:**
  - `"GERİLİM".lower()` sonucu `'geri̇li̇m'` olur ve `gerilim` ile eşleşmez; `casefold()` da eşleşmez (bu ortamda doğrulandı).
  - Türkçe bir EDAŞ dosyasında gerilim sütunu bulunamaz. Bu durumda tüm hatlar uyarısız `minor_line/mv/assumed` olur ve yanlış açıklık bandı kullanılır.
  - `hat_id` tekil değilse `line_id` ve dolayısıyla `segment_id` tekrarlanır. Hiçbir aşama tekilliği doğrulamıyor.
- **Düzeltme:**
  - Sütun adlarını NFKD ile normalleştirip ASCII'ye indir ve küçült; İ ve ı'yı i ile eşle.
  - Gerilim sütunu bulunamazsa uyarı ya da hata ver.
  - `build_segments` sonunda `segment_id.is_unique` koşulunu doğrula; yinelenen kimliklere ek indeks ver.

### O7. Model ve veri parametreleri koda gömülü
- **Yer:**
  - `rasters.py:17`: `AOI_BUFFER_M=1000`
  - `rasters.py:18`: `SCL_BAD`
  - `rasters.py:19`: `TPI_RADIUS_M=300`
  - `firms.py:38`: `MARGIN_KM=5`
  - `weather.py:38`: `GRID_KM=10`
  - `sentinel2.py:31`: `MAX_CLOUD=80`
  - `chm.py:530`: `zoom=10`
- **Sorun:**
  - Proje kuralına göre bu tür sayılar config'te durmalı.
  - TPI yarıçapı wind_exposure çarpanını belirliyor. AOI tamponu `buffers_m.fuel` (1000 m) için gereken kapsamı, FIRMS payı da `history_kernel` (2000 m) için gereken kapsamı sağlıyor.
  - Config'te bu tamponlardan biri büyütülürse kapsam sessizce yetersiz kalır. Örnek: `fuel` 1500 m yapılırsa AOI+1 km'lik WorldCover yetmez.
- **Düzeltme:**
  - Bu değerleri `config/aoi.yaml → ingest:` bölümüne taşı.
  - Başlangıçta şu koşulları doğrula: `AOI_BUFFER_M >= max(buffers_m.fuel, wui, slope, dryness)` ve `MARGIN_KM*1000 >= max(history_kernel, event_line_distance)`.

### O8. Strike-tree koşulu hattın altındaki alçak çalıyı da sayıyor (yöntem; spec düzeyi)
- **Yer:** `chm.py:189-199`. Kod spec §2 ile birebir uyumlu.
- **Sorun:**
  - Koşul h ≥ d + 1 m. d ≈ 0,5 m'de 1,5–2 m'lik maki de bu koşulu sağlıyor.
  - MAE ~2,8 m olduğundan küçük d'de sonuç gürültü baskın.
  - İletken yüksekliği hesaba katılmıyor; 154/380 kV iletkenleri yaklaşık 10 m'nin üstünde.
  - `chm_strike_clusters` (ortalama 1,8, en çok 11) ağaçtan çok çalı yoğunluğunu ölçüyor olabilir. Bu faktörün P içindeki ağırlığı 0,25.
- **Düzeltme:**
  - risk-modeler bir ADR yazsın: koşula `h >= strike_min_height_m` eklensin ya da gerilim sınıfına göre config'ten alınan iletken yüksekliği H_c ile `h >= sqrt(d² + H_c²)` kullanılsın.
  - Bu değişiklik için duyarlılık analizi yapılsın.

### O9. Test boşlukları kritik yolları kapsamıyor
- **Yer:**
  - `tests/ingest/test_rasters.py:24-29`: `normalized_difference` ve `valid_mask_from_scl` test ediliyor ama üretimde kullanılmıyor; `sentinel2.py:99-103`'teki satır içi xarray yolu testsiz.
  - `tests/test_pipeline.py:83-86`: test, canlı config değerine (`2026-10-30`) bağlı.
- **Eksik testler:**
  - CHM önbelleğinin parametre değişince geçersizleşmesi (Y1)
  - FIRMS önbelleğinin AOI'ye bağlı olması (Y2)
  - `http_get` istisna yolunda anahtar maskesi (requests ConnectionError iletisi URL'yi içerir)
  - Overpass `remark`
  - EDAŞ'ta Türkçe sütun adı ve kimlik tekilliği
  - Ölçek, ofset ve SCL maskesi uygulanmış S2 kompoziti
- **Düzeltme:**
  - İndeks hesabını saf bir fonksiyona taşı ve sentetik xarray ile test et.
  - Her Y ve O bulgusu için bir regresyon testi ekle.
  - Config'e bağlı testi geçici bir config dosyasıyla yaz.

### O10. Gün sınırı (UTC mi yerel mi) tanımsız
- **Yer:**
  - `firms.py:256`: UTC tarihine göre filtre
  - `weather.py:80`: yerel saat
  - `config/aoi.yaml:51-53` ve `:62`
- **Sorun:**
  - FIRMS tarihleri UTC, rüzgâr ve senaryo günleri yerel (UTC+3).
  - STATUS'taki "29 Haz 436 · 30 Haz 141 · 1 Tem 13" sayımı UTC gününe göre. Aynı tespitler yerel güne göre 418 / 155 / 15.
  - as_of, sezon sınırları ve "senaryo günü" eşleştirmesi bu tanıma bağlı.
- **Düzeltme:**
  - ADR ile tek bir tanım seç (öneri: yerel gün, Europe/Istanbul) ve FIRMS'e `acq_date_local` sütunu ekle.
  - STATUS'taki sayıya hangi gün tanımının kullanıldığını yaz.

## Düşük bulgular
| # | Yer | Sorun | Öneri |
|---|---|---|---|
| D1 | `rasters.py:18`, `sentinel2.py:99-103` | SCL 1 (doygun/kusurlu), 6 (su) ve 11 (kar) maskelenmiyor. Negatif yansıtım 0'a kırpıldığı için indeks ±1'e doyuyor: current NDMI'da piksellerin %4,5'i, koridorda 21.669 pikselin 50'si. 3 segmentin ±50 m koridorunun %30'undan fazlası kalıcı su (WorldCover 80) | SCL_BAD'e 1 ve 6'yı ekle. DN<1000 pikselleri kırpmak yerine NaN yap. fuel_dryness'ta WorldCover 80'i dışla |
| D2 | `sentinel2.py:116-120`, `dem.py:35`, `worldcover.py:43`, `buildings.py:203-208`, `common.py:137` | Önbellek anahtarlarında bbox, çözünürlük, sürüm ve parametreler yok. current_asof değişince backtest kompoziti de yeniden hesaplanıyor (~8 dk) | Her meta json'a `cache_key` yaz ve karşılaştır. Pencere başına ayrı önbellek tut |
| D3 | `firms.py:140-150`, `:146` | HTTP 400 kota sayılıyor; kalıcı 400'de 12×90 sn = 18 dk bekleniyor. `r.text[:60]` önce kesilip sonra maskeleniyor; kesim anahtarı bölerse kısmi anahtar loga düşer. urllib3 DEBUG açılırsa istek yolu, anahtar dahil, loglanır | Önce maskele, sonra kes. 400'ü yalnız gövdede "limit" geçiyorsa kota say. `logging.getLogger("urllib3").setLevel(WARNING)` |
| D4 | `lines.py:216-217`, `common.py:86-95` | MANIFEST, türetilmiş ürünleri koleksiyon düzeyinde URL ile tutuyor. FIRMS URL'si çağrılabilir değil (`_SP\|NRT/.../<yıl>`); gerçekte tüm satırlar SP. EDAŞ dosyası mutlak yerel yolla (kullanıcı adı dahil) commit'lenen MANIFEST'e her koşuda yazılıyor. Yazma atomik değil | `kind=derived` sütunu ekle. FIRMS için data_id ve tarih yaz. EDAŞ için göreli yol kullan, yalnız sha256 değişince kaydet. Geçici dosyaya yazıp `os.replace` ile değiştir |
| D5 | `weather.py:42-54`, `:80`, `:132` | 16 istek noktası 12 benzersiz Open-Meteo hücresine düşüyor; 4 seri yinelenmiş. UTC dönüşümü tz veritabanına dayanıyor. Senaryo eşiği config'te km/h, veri m/s | Yanıttaki lat/lon'a göre tekilleştir. `utc_offset_seconds` kullan. km/h→m/s dönüşümü F3'te tek yerde yapılsın. STATUS'a "12 benzersiz hücre" notu ekle |
| D6 | `dem.py:44-46`, `:53-55` | STAC aramasında yeniden deneme yok. `isel(time=0)` ve NaN→0 doldurma eksik bir karoyu sessizce 0 m'ye çevirir. Şu an sorun yok: AOI içinde yalnız 69 piksel 0 m | Yeniden deneme ekle. Zamanları birleştir. NaN payını logla, eşiği aşarsa hata ver |
| D7 | `dem.py:68-74`, `sentinel2.py:124-127` | UTM kutusunun yalnız iki köşesi lon/lat'a dönüştürülüyor. Menderes 27°E merkez meridyenine yakın olduğu için etkisi yok | `rasterio.warp.transform_bounds(..., densify_pts=21)` |
| D8 | `chm.py:222-226`, `:229-230` | İki EPSG de None ise CRS kontrolü farkı kaçırıyor. Bilinmeyen gerilim sınıfında sessizce `mv` varsayılıyor. `half_width >= strike_max_distance` doğrulanmıyor | `CRS.from_user_input(a) == CRS.from_user_input(b)` kullan. Bilinmeyen sınıfta hata ver. Bu koşulu doğrula |
| D9 | `lines.py:52-61` | OSM'de "34.5", "34,500" ya da "154 kV" gibi hatalı etiketler volt sanılıyor ve `lv/tag` olarak sınıflanıyor. Menderes verisinde böyle etiket yok (yalnız 154000 ve 380000) | "kv" birimi varsa ya da değer ondalıklı ve 1000'den küçükse ×1000 uygula, `voltage_source="tag_fixed"` yaz |
| D10 | `buildings.py:149-152` | DuckDB'de bellek sınırı yok; varsayılan RAM'in %80'i, kural ise 4 GB | `SET memory_limit='3GB'; SET threads=4` |
| D11 | `common.py:18` | USER_AGENT kişisel e-posta adresi içeriyor, commit'li ve tüm dış servislere gönderiliyor | Proje iletişim adresi kullan ya da `HATKALKANI_CONTACT` ortam değişkeninden oku |
| D12 | `docs/ATTRIBUTIONS.md:11`, `:15` | FIRMS satırında NASA'nın önerdiği teşekkür metni yok. DEM resmi atıf metni bekliyor (ATTR-1). Open-Meteo arşivinin altındaki ERA5 için Copernicus C3S atfı gerekebilir | ATTR-1 doğrulasın. Aday metinler: FIRMS "We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS), part of NASA's ESDIS"; DEM "© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA" |
| D13 | `lines.py`, `buildings.py` | Backtest için kullanılan vektör katmanlar as_of'tan sonraki tarihli: OSM osm_base 2026-10-30T17:49Z, Overture 2026-10-21.0. WorldCover (2021) ve CHM (v1 referansı 2016–2020) ise as_of'tan önce | MODEL_CARD'a yaz. İstenirse backtest hatlarını Overpass `[date:"2025-05-31T00:00:00Z"]` ile çek |
| D14 | `config/aoi.yaml:9-10` | Pilot 2025 yangınları nedeniyle seçildi ve aynı sezon backtest olayı olarak kullanılıyor; değerlendirme seçimden bağımsız değil | MODEL_CARD'a sınır olarak yaz: lift'in genellenebilirliği sınırlı |
| D15 | `chm.py:423`, `:531`, `:590`; `sentinel2.py:104-105`; `lines.py:196-199`; `chm.py:452-457` | `shapely.ops.transform` kullanımdan kalkıyor. `PYTHONUTF8` çalışan süreci etkilemiyor. NDVI ve NDMI için iki ayrı `compute`, S3'ten iki kez okuyor. Birden çok EDAŞ dosyası varsa yalnız ilki sessizce alınıyor. "≈8 MB" bir alt sınır tahmini | `shapely.transform` kullan. Tek `compute` yap. Birden çok dosyada uyar. ADR-008'de "≈8 MB" yerine "en az ≈8 MB" yaz |

## Sayıların kaynağı (dürüstlük kontrolü)
STATUS ve ATTRIBUTIONS'taki sayılar çıktılardan yeniden hesaplandı:

| İddia | Kaynak dosya | Sonuç |
|---|---|---|
| Sınır 787,2 km² | boundary.parquet `area_km2` | Doğru |
| 17 hat, 92,4 km; ≥154 kV 61,0 km; etiketsiz 31,5 km | lines.parquet | Doğru |
| 925 segment; 58–142 m; medyan 100 m | segments.parquet | Doğru |
| CHM p90 medyanı 2,0 m; ortalama 3,7; en yüksek 27; max'ın medyanı 7 m | chm_segment_stats.parquet | Doğru |
| 65.873 bina; Microsoft %87,3, OSM %12,7; hatlara 300 m içinde 3.633 | buildings_meta.json, buildings.parquet | Doğru |
| Lisans "ODbL / CDLA-Permissive-2.0" | ham Overture `license` alanı | **Yanlış** (Y3) |
| 3.180 FIRMS tespiti; yıllık sayılar; 2025'te 982 | firms.parquet | Doğru |
| 29.06.2025 ±2 gün: 590 (436 / 141 / 13) | firms.parquet | Doğru, ancak UTC gününe göre (O10) |
| En yüksek hamle 15,2 / 19,8 / 24,0 / 19,5 m/s | wind_hourly.parquet | Doğru; "16 nokta" aslında 12 benzersiz hücre (D5) |
| S2: 24 sahne / 13 gün ve 21 sahne / 12 gün | s2_meta.json | Doğru |
| "v2'de görüntü tarihi yok" | F1-2 raporuna göre `metadata/` incelenmedi | Doğrulanmamış (O2) |

## Olumlu yönler
- Saf hesap ile G/Ç ayrımı tutarlı. CRS her fonksiyonda kontrol ediliyor. Uzunluklar ve tamponlar metrik CRS'de hesaplanıyor.
- CHM'de pencereli okuma, seyrek ara dosya ve tile HEAD kontrolü iyi kurulmuş. NaN olan istatistiklerin nedeni (`chm_nan_reason`) kaydediliyor.
- FIRMS anahtarı yalnız ortamdan okunuyor. MANIFEST'e sabit `***` yazılıyor. İstisna iletileri maskeleniyor.
- Open-Meteo birimi açıkça isteniyor ve dönüşüm sütun adına yansıtılıyor.
- S2 güncel penceresinin `current_asof` ile sabitlenmesi önbelleğin her gün bozulmasını önlüyor.
- Pipeline'ın sonundaki MANIFEST doğrulaması (yinelenen satır, eksik dosya, sha256) değerli bir güvence.
