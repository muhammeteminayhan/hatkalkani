# F3-1: `as_of` parametreli özellikler ve zaman sızıntısı testi

- **Model:** claude-opus-5-5 (Opus 5.5), risk-modeler
- **Tarih:** 2026-10-31
- **AOI:** `izmir_menderes`: 925 segment, 17 hat (921 hv, 4 mv)
- **Kapsam:** risk-model-spec §2 özellikleri. Skor, kademe ve iş paketi F3-2'de; olay sayısı ve lift F3-3'te üretilecek. Bu yüzden bu raporda kademe dağılımı, skor dağılımı, olay sayısı ve lift yok.
- **Kararlar:** ADR-009 (docs/DECISIONS.md).

## Özet
- **Faktörler:** Dokuz faktör tek bir kayıtta (`FACTORS`). Her faktör tek bir fonksiyon ve zorunlu `as_of` parametresi alıyor. Kayıt, `risk_weights.yaml` ile çalışma anında karşılaştırılıyor.
- **Çıktılar:** İki as_of için 925'er satır üretildi.
  - Tek veri kaynaklı NaN, `187664557_0019` segmentinde: ±50 m koridorun tamamı su olduğu için `fuel_dryness:all_water`.
  - `asset_condition` için veri yok ve ağırlığı 0. Bu faktör `unavailable` olarak işaretli.
  - Nedeni yazılmamış bir NaN build'i durdurur.
- **Zaman sızıntısı:** Kesimden sonraki FIRMS, rüzgâr ve S2 verisi sentetik olarak eklendiğinde çıktı bayt bayt aynı kalıyor. Aynı veri kesimden önce eklendiğinde çıktı değişiyor (pozitif kontrol).
  - Ayrıca her zamana bağlı faktör `max_time_used_utc` bildiriyor. Bu değer kesimi aşarsa build `TemporalLeakageError` ile duruyor.
- **CHM çalışma anı doğrulaması:**
  - Kontroller: dtype `uint8`, nodata 255, ölçek 1, ofset 0, CRS, kare piksel ve değer aralığı 0–100 m.
  - Gerçek veride geçerli piksel yükseklikleri 0–32 m (p50 0, p90 4, p99 17).
  - Bağımsız uygulama, ingest'in `chm_segment_stats` çıktısıyla tam örtüşüyor: 925/925, fark 0.
- **Önemli bulgular:**
  - `wind_exposure` neredeyse tümüyle topoğrafyadan geliyor (ρ = 0,984).
  - `strike_trees` kümelerinin %34'ünün en yüksek pikseli 4 m'nin altında (O8 doğrulandı).
  - Sonuç (C) faktörleri birbirine güçlü bağlı.
  - `fuel_dryness` iki as_of arasında yalnız ρ = 0,51 tutarlı.
- **Bütçe:** `--stage features` iki as_of için 13,6 sn sürüyor; tepe bellek 297 MB. Yeniden çalıştırmada iki dosyanın SHA-256 değeri aynı.

## Çalıştırma
```
uv run python scripts/run_pipeline.py --aoi izmir_menderes --stage features   # iki as_of (config)
uv run python -m hatkalkani.features.build --aoi izmir_menderes --as-of 2025-05-31
uv run python -m hatkalkani.features.build --aoi izmir_menderes --as-of backtest current
uv run python notebooks/f3_1_feature_summary.py --aoi izmir_menderes          # bu rapordaki tablolar
```
- `--stage all` sırasıyla ingest, MANIFEST denetimi ve özellikleri çalıştırır.
- `--stage ingest` değişmedi.
- Ingest çıktısı eksikse özellik aşaması hiç başlamadan durur.

## Çıktı şeması: `data/processed/<aoi>/features_<as_of>.parquet`
- **Taban sütunlar:** `segment_id`, `line_id`, `voltage_level`, `length_m`, `as_of`. Satır sırası segments.parquet ile aynıdır.
- **Faktör sütunları:** Dokuz faktörün normalize edilmemiş ham değeri; sütun adı faktör adıdır.
- **`nan_reasons`:** `faktör:neden` biçiminde, `;` ile ayrılır. NaN yoksa boş kalır. `unavailable` faktörler bu sütuna yazılmaz.
- **`aux_*`:** Açıklayıcı yardımcı sütunlar, örneğin `aux_wind_gust_p95_ms`, `aux_tpi_m`, `aux_wui_buildings` ve `aux_strike_tall_clusters`.
- **Metaveri:** Parquet içinde `hatkalkani_features` anahtarında ve okunabilir bir `.meta.json` eşinde tutulur. İçerik:
  - as_of, kesim ve gün sınırı;
  - faktör kaydı;
  - kaynak başına provenance (pencere, sayımlar, `max_time_used_utc`);
  - NaN sayımları;
  - girdi SHA-256'ları;
  - config anlık görüntüsü.
- **Okuma:** `hatkalkani.features.build.read_features(path)`.

## Faktör kaydı
| faktör | etiket | bileşen | birim | yön* | zaman | kaynak |
|---|---|---|---|---|---|---|
| `vegetation_encroachment` | Hatta yakın yüksek ağaç | ignition | oran (0-1) | higher | static | CHM v2 (1 m) + gerilim sınıfı |
| `strike_trees` | Hatta devrilebilecek ağaç | ignition | küme sayısı | higher | static | CHM v2 (1 m) |
| `fuel_dryness` | Kuru bitki örtüsü | ignition | NDMI (-1..1) | **lower** | time_filtered | S2 L2A NDMI medyanı (20 m) + WorldCover su maskesi |
| `wind_exposure` | Rüzgâra açıklık | ignition | m/s (hamle p95 × çarpan) | higher | time_filtered | Open-Meteo saatlik hamle + DEM TPI |
| `fuel_continuity` | Kesintisiz orman/maki | consequence | oran (0-1) | higher | static | WorldCover 2021 (10 m) |
| `slope` | Dik yamaç | consequence | derece | higher | static | Copernicus DEM GLO-30 eğim |
| `wui_exposure` | Yerleşime yakınlık | consequence | log1p(bina) | higher | static | Overture binaları |
| `fire_history` | Geçmiş yangın yoğunluğu | consequence | hücre-gün/km² | higher | time_filtered | FIRMS VIIRS (S-NPP + NOAA-20) |
| `asset_condition` | Tesis durumu | consequence | – | higher | unavailable | EDAŞ varlık verisi (yok) |

\* "lower": düşük ham değer daha riskli demektir. F3-2'deki yüzdelik adımı bu faktörün yönünü çevirir.

| faktör | ham tanım | as_of kuralı |
|---|---|---|
| vegetation_encroachment | Açıklık bandındaki (`clearance_band_m`, yer tutucu) geçerli CHM piksellerinden yüksekliği ≥ 4 m olanların oranı | Statik taban. CHM v2 görüntü tarihi bilinmiyor (ADR-008); filtrelenemez, sınırlama olarak yazılır |
| strike_trees | ±30 m'de h ≥ d + 1 m koşulunu sağlayan, 8-komşulukla bağlı ≥ 4 px küme sayısı | Aynı |
| fuel_dryness | ±50 m düz uçlu koridorda, su olmayan geçerli NDMI piksellerinin medyanı | Penceresi as_of günü ya da öncesinde biten ve tüm sahneleri kesimden önce olan en son kompozit; sahne tarihleri `s2_meta.json` ile kanıtlanır |
| wind_exposure | En yakın Open-Meteo hücresinin hamle p95 değeri × (0,5 + segment TPI'sinin AOI TPI dağılımındaki yüzdeliği) | 2022–2024'ün Haziran–Eylül saatleri (yerel takvim) ve kesimden önceki kayıtlar; senaryo günleri dışarıda |
| fuel_continuity | 1000 m yuvarlak tamponda WorldCover ağaç (10) + çalılık (20) oranı | Statik (2021) |
| slope | ±100 m düz uçlu koridorda ortalama eğim | Statik |
| wui_exposure | 500 m yuvarlak tamponda temsil noktası kalan bina sayısının log1p'si | Statik vekil; Overture sürümü 2026-10-21, as_of'tan sonra |
| fire_history | (yerel gün, 375 m hücre) başına tekilleştirilmiş VIIRS tespitlerinin quartic çekirdek yoğunluğu (h = 2000 m, segment orta noktası) | `firms_history[0]` yerel gün başından as_of kesimine kadar |
| asset_condition | – | Veri yok |

## as_of kuralı ve sızıntı denetimi (ADR-009)
- **Gün sınırı:** as_of günü Europe/Istanbul yerel takvimine göre dahil. Kesim (hariç) as_of+1 günü 00:00 yerel saattir. 2025-05-31 için bu 2025-05-31 21:00 UTC; 2016 öncesi kış tarihlerinde UTC+2 uygulanır. Saat dilimsiz zaman damgası reddedilir.
- **Gerçek veride kesimin etkisi:**

| as_of | FIRMS VIIRS | S2 | rüzgâr |
|---|---|---|---|
| 2025-05-31 | 1.719 tespit → 1.250 hücre-gün, son 2025-05-28; kesim sonrası 788 tespit dışlandı | backtest (2025-04-15..05-31), 24 sahne, son sahne 05-31 09:10 UTC | 2022–24 Haz–Eyl, 12 hücre × 8.784 saat; 1.536 senaryo saati dışarıda |
| 2026-10-30 | 2.507 → 1.742 hücre-gün, son 2025-09-23. **Ingest kapsamı 2025-09-30'da bitiyor: 395 günlük boşluk** | current (2026-09-15..10-30), 21 sahne, son sahne 10-25 | aynı (config 2025 yazını içermiyor) |

- **Testler (`tests/features/test_leakage.py`, 8 test):**
  - **Gelecek verisi:** Her segment orta noktasına kesimdeki, ertesi sabahki, sezon içi ve bir yıl sonraki VIIRS tespitleri (NRT dahil) eklendi. Kesim sonrası tüm rüzgâr saatleri 99 m/s yapıldı. Biri penceresi as_of'tan sonra biten, diğeri penceresi as_of'ta bitip bir sahnesi kesimden sonra olan iki "geç" S2 kompoziti eklendi. Sonuçta çıktı `assert_frame_equal` ile birebir aynı.
  - **Pozitif kontroller:**
    - Kesimden 1 dakika önceki bir tespit fire_history'yi artırıyor.
    - as_of 2023-07-15 iken kesimden sonraki fırtına özelliği değiştirmiyor, iki hafta önceki fırtına p95'i yükseltiyor.
    - Daha geç bir as_of daha geç kompoziti seçiyor.
  - **Çalışma anı koruması:** Provenance'ı kesimde ya da sonrasında olan bir faktör `TemporalLeakageError` veriyor. `max_time_used_utc` bildirmeyen zamana bağlı bir faktör `FeatureBuildError` veriyor.
  - **Sınır değerleri:** `test_asof.py` 20:59:59Z, 21:00:00Z, NaT ve 2015 kışı (UTC+2) durumlarını sınıyor.

## Dağılımlar
**as_of 2025-05-31** (n = 925)

| faktör | n | nan | sıfır | ort | std | min | p10 | p25 | p50 | p75 | p90 | p95 | max | tekil |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vegetation_encroachment | 925 | 0 | 438 | 0.080 | 0.165 | 0 | 0 | 0 | 0.002 | 0.071 | 0.273 | 0.459 | 1.00 | 384 |
| strike_trees | 925 | 0 | 327 | 1.79 | 1.95 | 0 | 0 | 0 | 1.00 | 3.00 | 5.00 | 5.00 | 11.00 | 11 |
| fuel_dryness | 924 | 1 | 0 | 0.112 | 0.125 | -0.232 | -0.068 | 0.050 | 0.122 | 0.195 | 0.259 | 0.294 | 0.468 | 923 |
| wind_exposure | 925 | 0 | 0 | 13.61 | 3.65 | 7.12 | 9.19 | 10.81 | 13.08 | 15.94 | 18.89 | 20.41 | 24.31 | 925 |
| fuel_continuity | 925 | 0 | 0 | 0.540 | 0.315 | 0.004 | 0.105 | 0.219 | 0.618 | 0.825 | 0.931 | 0.950 | 0.990 | 924 |
| slope | 925 | 0 | 0 | 9.18 | 7.61 | 0.053 | 0.513 | 1.28 | 8.22 | 15.60 | 20.00 | 22.34 | 32.01 | 925 |
| wui_exposure | 925 | 0 | 99 | 2.86 | 1.87 | 0 | 0 | 1.10 | 2.77 | 4.75 | 5.37 | 5.55 | 6.14 | 241 |
| fire_history | 925 | 0 | 135 | 1.25 | 1.75 | 0 | 0 | 0.066 | 0.481 | 1.64 | 4.37 | 5.84 | 6.46 | 791 |
| asset_condition | 0 | 925 | – | – | – | – | – | – | – | – | – | – | – | – |

**as_of 2026-10-30.** Yalnız değişen satırlar gösteriliyor; diğer faktörler birebir aynı.

| faktör | n | nan | sıfır | ort | std | min | p10 | p25 | p50 | p75 | p90 | p95 | max | tekil |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fuel_dryness | 924 | 1 | 0 | 0.062 | 0.121 | -0.182 | -0.069 | -0.032 | 0.039 | 0.142 | 0.235 | 0.298 | 0.432 | 923 |
| fire_history | 925 | 0 | 126 | 1.29 | 1.76 | 0 | 0 | 0.090 | 0.481 | 1.76 | 4.37 | 5.84 | 6.46 | 800 |

**Yardımcı sütunlar** (as_of 2025-05-31)

| sütun | p10 | p50 | p90 | max | not |
|---|---|---|---|---|---|
| aux_chm_band_px | 998 | 1000 | 1002 | 1421 | hv bandı ±5 m × ~100 m |
| aux_chm_valid_frac | 1.00 | 1.00 | 1.00 | 1.00 | 925 segmentin tamamında CHM kapsaması tam |
| aux_strike_tall_clusters | 0 | 1 | 3 | 10 | 444 segmentte 0 |
| aux_ndmi_px | 24 | 25 | 26 | 36 | 1 segmentte 0 (su) |
| aux_ndmi_water_px_excluded | 0 | 0 | 0 | 25 | 4 segmentte > 0 |
| aux_wind_gust_p95_ms | 12.69 | 13.69 | 14.50 | 16.39 | yalnız 8 farklı değer |
| aux_tpi_m | -13.06 | -0.22 | 15.73 | 57.36 | |
| aux_topo_multiplier | 0.648 | 1.00 | 1.37 | 1.50 | min 0,503 |
| aux_fuel_tree_frac / shrub | 0.075 / 0.019 | 0.460 / 0.062 | 0.857 / 0.264 | 0.941 / 0.375 | |
| aux_fuel_coverage | 1.00 | 1.00 | 1.00 | 1.00 | min 0,999 (tampon tam kapsanıyor) |
| aux_wui_buildings | 0 | 15 | 213 | 461 | 99 segmentte 0 |
| aux_fire_cell_days_in_kernel | 0 | 7 | 52 | 71 | 135 segmentte 0 |

## Eksik değerler
| faktör | neden | sayı | açıklama |
|---|---|---|---|
| fuel_dryness | `all_water` | 1 (iki as_of'ta da) | `187664557_0019` (154 kV; orta nokta 38,136 K, 27,091 D): ±50 m koridorun 100 WorldCover pikselinin tamamı su (80). Bitki yok, kuruluk tanımsız |
| asset_condition | `no_data_source` | 925 | Pilotta EDAŞ verisi yok; ağırlık 0 (`unavailable_factors`) |

Diğer faktörlerde NaN yok. Yardımcı sütunlarda yalnızca, ilgili faktörün NaN olduğu yerde NaN olabilir; bu kural build'de denetleniyor.

## İki as_of arasındaki fark
| faktör | özdeş | değişen segment | Spearman | medyan 2025-05-31 → 2026-10-30 |
|---|---|---|---|---|
| fuel_dryness | hayır | 924 | 0,505 | 0,122 → 0,039 |
| fire_history | hayır | 204 | 0,995 | 0,481 → 0,481 |
| diğer 6 faktör | evet | 0 | 1,00 | aynı |

- **fuel_dryness:** Backtest bahar (Nis–May) kompozitini, güncel harita sonbahar (Eyl–Eki) kompozitini kullanıyor. İki kompozit mevsim olarak farklı: sıralama yalnız ρ = 0,51 ile tutarlı ve medyan NDMI 0,12'den 0,04'e iniyor. Bu fark beklenen bir sonuç, sızıntı değil. Ancak geriye dönük testte doğrulanan "kuruluk" güncel haritadakiyle aynı mevsim değil.
- **fire_history:** 2025 sezonu güncel haritada geçmişe giriyor; 204 segmentin yoğunluğu artıyor. Tespitler 2025-09-30'da kesildiği için güncel haritada son 13 ayın yangınları eksik.

## Faktörler arası ilişki (Spearman, as_of 2025-05-31)
| | enc | strike | dry(NDMI) | wind | fuel | slope | wui | fire |
|---|---|---|---|---|---|---|---|---|
| vegetation_encroachment | 1 | 0,68 | 0,26 | -0,11 | 0,28 | 0,34 | -0,17 | 0,02 |
| strike_trees | | 1 | 0,27 | -0,17 | 0,39 | 0,38 | -0,20 | -0,07 |
| fuel_dryness (NDMI) | | | 1 | -0,13 | 0,44 | 0,44 | -0,32 | -0,05 |
| wind_exposure | | | | 1 | -0,06 | 0,05 | -0,01 | 0,00 |
| fuel_continuity | | | | | 1 | 0,74 | -0,63 | -0,21 |
| slope | | | | | | 1 | -0,63 | 0,05 |
| wui_exposure | | | | | | | 1 | -0,02 |

Okuma notları:
- **NDMI ile örtü:** NDMI ham değeriyle ormanlık ve dik alanlar arasındaki ilişki pozitif (0,44): yeşil örtü nemli görünüyor. `fuel_dryness` yüzdeliği ters çevrildiğinde, kuruluk bu faktörlerle negatif ilişkili olacak.
- **C bileşeni:** C içinde `fuel_continuity` ile `slope` aynı yöne gidiyor (0,74). `wui_exposure` ise ikisine de ters (-0,63): orman yerleşimden uzak. C, birbirine karşı çalışan iki sinyali topluyor.
- **wind_exposure:** Diğer faktörlerden bağımsız. Ama bu bağımsızlık rüzgârdan değil topoğrafyadan geliyor (aşağıya bakın).

## Doğrulama
- **CHM çalışma anı doğrulaması (REV-F2 O1):**
  - `validate_chm_profile` şunları denetliyor: tek bant, `uint8`, nodata 255, ölçek (1,0), ofset (0,0), kare piksel, metrik CRS.
  - `check_chm_values` her pencerede geçerli değerlerin 0–100 m aralığında olduğunu doğruluyor. Desimetre ya da yanlış ölçek, örneğin 15 m'lik bir çamın 150 görünmesi, hata verir.
  - Gerçek veride okunan 5.547.295 geçerli pikselin yükseklik dağılımı p50/p90/p99/max = 0/4/17/32 m.
  - Testler: uint16, nodata 0, ölçek 0,1, yanlış CRS ve 150 m değer reddediliyor.
- **Bağımsız çapraz kontrol:** `vegetation_encroachment` ile ingest'in `chm_encroach_frac` alanı arasındaki en büyük fark 0. `strike_trees` ile `chm_strike_clusters` 925/925 segmentte eşit.
- **Sentetik uçtan uca testler (`test_factors.py`):** Her faktör elle tasarlanmış verideki beklenen değeri veriyor. Beklenen değerler kodun kendisinden değil, bağımsız hesaplardan geliyor: shapely alanları, kaba kuvvet mesafeler ve açık yazılmış çekirdek formülü. Su maskesi olmasa sonuç -0,1 çıkardı; maskeyle -0,2.
- **CHM parametre duyarlılığı (±%20):** Değerler yer tutucu, config değiştirilmedi.

| varyant | enc ρ | enc üst-%20 örtüşme | strike ρ | strike üst-%20 örtüşme |
|---|---|---|---|---|
| bantlar −%20 (lv 0,8 / mv 2,4 / hv 4 m) | 0,990 | 0,984 | 1,000 | 1,000 |
| bantlar +%20 (1,2 / 3,6 / 6 m) | 0,992 | 0,973 | 1,000 | 1,000 |
| min_encroach_canopy_m 3,2 m | 1,000 | 1,000 | 1,000 | 1,000 |
| min_encroach_canopy_m 4,8 m | 0,933 | 0,909 | 1,000 | 1,000 |
| strike_margin_m 0,8 m | 1,000 | 1,000 | 0,959 | 0,938 |
| strike_margin_m 1,2 m | 1,000 | 1,000 | 0,990 | 0,865 |
| strike_min_cluster_px 3 | 1,000 | 1,000 | 0,990 | 1,000 |
| strike_min_cluster_px 5 | 1,000 | 1,000 | 0,991 | 0,888 |

Okuma notları:
- Yer tutucu bant genişlikleri sıralamayı neredeyse hiç etkilemiyor.
- CHM tam sayı metre olduğu için 3,2 m eşiği 4 m ile, 4,8 m eşiği 5 m ile aynı sonucu veriyor.
- `strike_trees`'in üst %20'si, kenar boşluğu ve küme boyutuna karşı daha hassas (örtüşme 0,87–0,94).

## Sınırlamalar
1. **CHM taban yılı bilinmiyor (ADR-008).** v1 referansı 2016-07..2020-02. CHM özellikleri as_of ile filtrelenemiyor; görüntü as_of'tan sonraysa sızıntı, çok eskiyse bayatlık riski var. 2019'da büyük yangınlar oldu. Metaveride `temporal_status: undated_static_baseline` yazılı. CHM'nin MAE'si ~2,8 m; tek piksel değil küme sayılıyor. Yine de 4 m eşiği MAE'ye yakın.
2. **Açıklık bantları yer tutucu** (`placeholder_unverified: true`). Bu durum metaveriye taşınıyor. Duyarlılığı düşük (yukarıda).
3. **strike_trees çalıyı da sayıyor (REV-F2 O8, doğrulandı).** 1.660 kümenin yalnız 1.095'inde (%66) en yüksek piksel ≥ 4 m. 117 segmentte strike > 0 ama ≥ 4 m'lik küme yok. İletken yüksekliği hesaba katılmıyor.
4. **wind_exposure fiilen bir topoğrafya faktörü.** Spearman, TPI çarpanıyla 0,984, hamle p95 ile 0,008. Hamle p95'in segmentler arasında yalnız 8 farklı değeri var (12,3–16,4 m/s). Bunun nedeni Open-Meteo'nun ~10 km'lik ve 12 tekil hücresi. 2025 yazı klimatolojiye alınmıyor (config).
5. **fuel_dryness mevsime bağlı.** Backtest bahar, güncel harita sonbahar kompoziti (yukarıdaki ρ 0,51).
   - Yapı ve çıplak alan pikselleri maskelenmiyor; NDMI'si düşük olduğu için "kuru" görünebilir.
   - SCL 1 ve 6 ingest'te maskelenmiyor (D1). Su, WorldCover maskesiyle kısmen dışlanıyor.
6. **FIRMS:**
   - Tespitler tutuşma noktası değil; piksel ~375 m.
   - Tarım yakmaları gürültü katıyor.
   - Ingest `type` alanını taşımıyor; statik endüstriyel kaynaklar ayıklanamıyor.
   - Güncel as_of için son 395 gün eksik.
   - Etkisi küçük tutulmalı (ağırlık 0,10).
7. **Vektör katmanların tarihi:** OSM hatları (2026-10-30) ve Overture binaları (2026-10-21) backtest as_of'undan sonra (D13). Yapı stoğu yavaş değişiyor ama hat geometrisinin 2025'te aynı olduğu doğrulanmadı.
8. **Gerilim sınıfı:** Segmentlerin 921'i hv, 4'ü mv; mv istatistikleri anlamlı değil. Dağıtım şebekesi için sonuç iddia edilmez (ADR-007).

## F3-2 ve sonrası için öneriler
Config değiştirilmedi. Ağırlık ve eşik değişiklikleri için orkestratör onayı gerekir.
- **Normalizasyon bağları:** `vegetation_encroachment`'ta 438 segment (%47) ve `strike_trees`'te 327 segment 0. `strike_trees`'in yalnız 11 farklı değeri var. Yüzdelik sırada ortalama sıra (`method="average"`) kullanılmalı; aksi halde sıfırlar keyfi sıralanır.
- **NaN politikası:**
  - `all_water` için en düşük kuruluk riski önerilir (ters yüzdelik 0). Bitki yok; faktör fiziksel olarak sıfıra yakın.
  - `asset_condition` ağırlığı 0; skorda atlanmalı.
- **O8 için ADR adayı:** strike koşuluna küme tepe yüksekliği ≥ `min_encroach_canopy_m` şartı eklenebilir. Yeni config sayısı gerekmez. `aux_strike_tall_clusters` bu tanımı zaten hesaplıyor; geçiş tek satırlık bir değişiklik. Önce F3-3'te iki tanımın lift'i karşılaştırılmalı.
- **wind_exposure:**
  - Ya arayüzde "rüzgâra topoğrafik açıklık" olarak adlandırılmalı ve ağırlığı 0,15'te kalmalı.
  - Ya da hamle bileşeni için daha ince bir model gerekir (ör. ERA5-Land ya da yerel istasyon).
  - Senaryo motoru (F3-4) günlük hamleyi ayrıca kullandığı için çift sayım riski düşük.
- **C bileşeni:** `wui_exposure` ile `fuel_continuity`/`slope` arasındaki ters ilişki (-0,63) nedeniyle C dar bir aralıkta toplanabilir. F3-2'de ±%20 ağırlık duyarlılığına C'nin dağılımı da eklenmeli.
- **Sızıntı testi:** F3-2'de skor düzeyinde de bir sızıntı testi olmalı: as_of sonrası sentetik nokta → `risk` değişmez. F3-1 testleri buna hazır bir fixture sunuyor (`tests/features/synth.py`).
- **Spec sabitlerini config'e taşıma (öneri):** Haziran–Eylül, p95, 0,5–1,5 çarpanı, VIIRS 375 m, WorldCover sınıfları, CHM üst sınırı 100 m ve yerel saat dilimi. `firms_history[1]` alanının anlamı "ingest alt sınırı" olarak yeniden adlandırılabilir (ADR-009).

## Ingest'e devredilecek eksikler (data-engineer, orkestratör üzerinden)
- **FIRMS kapsamı:** Veri `periods.current_asof`'a kadar (NRT ile) uzatılmalı. Şu an güncel haritada 2025-10-01..2026-10-30 eksik.
- **FIRMS `type` alanı:** SP ürünlerindeki `type` alanı (0 bitki yangını, 2 statik kaynak) `firms.parquet`'e taşınmalı.
- **Rüzgâr:** Güncel harita için 2025 yazını klimatolojiye eklemek config kararıdır. Eklenirse `wind_hourly.parquet` 2025 Haziran–Eylül'ü içermeli; şu an yalnız 27–30 Haziran var.
- **Backtest hatları (isteğe bağlı):** Overpass `[date:"2025-05-31T00:00:00Z"]` ile çekilebilir (D13).

## Değişen ve eklenen dosyalar
- **Paket `src/hatkalkani/features/`:** `__init__.py`, `asof.py`, `registry.py`, `context.py`, `compute.py`, `rasterops.py`, `factors.py`, `build.py`.
- **`scripts/run_pipeline.py`:** `--stage features|all` eklendi; ingest yolu değişmedi.
- **Testler:**
  - `tests/features/`: 67 test, sentetik AOI `synth.py` içinde.
  - `tests/model/test_model_package.py`: F3-2 öncesi yer tutucu, 2 test.
- **Not defteri:** `notebooks/f3_1_feature_summary.py` (bu rapordaki tablolar).
- **Veri:** `data/processed/izmir_menderes/features_2025-05-31.parquet` ve `features_2026-10-30.parquet`, her biri `.meta.json` eşiyle.
- **`docs/DECISIONS.md`:** ADR-009 eklendi.

## Doğrulama komutları
| komut | sonuç |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run pytest tests/features tests/model -q` | 69 passed |
| `uv run pytest -q` | 121 passed, 2 deselected (ağ); 1 uyarı (`ingest/chm.py` shapely DeprecationWarning, F3-1 dışı) |
| `uv run python scripts/run_pipeline.py --aoi izmir_menderes --stage features` | rc 0; 13,6 sn; tepe bellek 297 MB; yeniden çalıştırmada SHA-256 aynı |
