# F3-2: Segment risk skoru, kademeler, ilk 3 neden ve iş paketleri

- **Model:** claude-opus-5-5 (Opus 5.5), risk-modeler
- **Tarih:** 2026-10-31
- **AOI:** `izmir_menderes`: 925 segment, 17 hat (921 hv, 4 mv). Hatların çoğu ≥154 kV iletim hattıdır; dağıtım şebekesi için sonuç iddia edilmez (ADR-007).
- **Kapsam:** risk-model-spec §3 (skor, kademe, top_factors) ve §4 (iş paketleri, dışa aktarım). Geriye dönük test (olay sayısı, lift, güven aralığı, taban çizgileri) F3-3'te yapılacak. **Bu rapordaki skorlar henüz olaylarla doğrulanmadı.** Yüksek skor bir öncelik sırasıdır; tespit değildir.
- **Kararlar:** ADR-010 (docs/DECISIONS.md). config/ değiştirilmedi.

## Özet
- **Çıktılar:** İki as_of için 925'er skor ve kademe üretildi:
  - Backtest haritası: 2025-05-31.
  - Güncel harita: 2026-10-30. Bu harita, FIRMS uzatması (F2-5b) bitmeden önceki özellik dosyasından üretildi; FIRMS'in son 395 günü eksik.
- **Kademeler:** Dağılım tam olarak config yüzdelikleriyle aynı: kritik 46 (%5,0) · yüksek 139 (%15,0) · orta 278 (%30,1) · düşük 462 (%49,9).
- **Skor aralığı:** Skor 0–100 ölçeğinde ama fiilen 16,5–79,0 arasında kalıyor (medyan 48,7). Kademe görelidir: kritik, "ilçedeki en yüksek %5" demektir; mutlak bir tehlike düzeyi değildir.
- **İlk 3 neden:**
  - Katkı, tipik bir segmente (tüm faktörler %50'lik dilimde, skor 50) göre puan farkının Shapley değeridir. Katkıların toplamı skor − 50'ye eşittir.
  - Kritik segmentlerde 1. neden çoğunlukla "Hatta yakın yüksek ağaç" (46 segmentin 29'u), sonra "Kesintisiz orman/maki" (11).
- **İş paketleri:** Backtest'te 72 açıklık (18,5 km), güncel haritada 76 açıklık (18,4 km). En uzun açıklık 1,6–1,7 km.
- **Sağlamlık:** Tek bir ağırlık ±%20 değişince:
  - Spearman ≥ 0,995,
  - üst-%20 örtüşmesi ≥ 0,935,
  - üst-%5 (kritik) örtüşmesi ≥ 0,913.

  Geometrik yerine doğrusal birleştirme sıralamayı daha çok değiştiriyor: üst-%5 örtüşmesi 0,80–0,85.
- **Zaman sızıntısı:** as_of sonrasına ait FIRMS, rüzgâr ve S2 verisi eklenince skor, kademe, top_factors ve iş paketleri birebir aynı kalıyor. Kesimden önceye eklenen tespitler ise skoru artırıyor (pozitif kontrol).
- **Bütçe:**
  - `--stage score` iki as_of için 2,9 sn sürüyor; tepe bellek 188 MB.
  - Yeniden çalıştırmada 10 dosyanın SHA-256 değeri aynı. GPKG'ler bu karşılaştırmaya girmiyor, çünkü yazım zaman damgası içeriyorlar.

## Çalıştırma
```
uv run python scripts/run_pipeline.py --aoi izmir_menderes --stage score    # iki as_of (config)
uv run python -m hatkalkani.model.run --aoi izmir_menderes --as-of backtest current
uv run python notebooks/f3_2_score_summary.py --aoi izmir_menderes          # bu rapordaki tablolar
```
- `--stage score` yalnız önbellekteki `features_<as_of>.parquet` dosyalarını okur; özellikleri yeniden üretmez.
- Özellik dosyası eksikse hiçbir şey çalıştırmadan durur.
- `--stage all` artık şu sırayla çalışır: ingest → MANIFEST → features → score.

## Yöntem (ADR-010)
1. **Normalizasyon:** Her faktör orta-sıra AOI yüzdeliğine çevrilir: (altındaki değer sayısı + 0,5 × eşit değer sayısı) / n.
   - Bağlı değerler aynı değeri alır. Örneğin `vegetation_encroachment` sıfırlarının hepsi 0,237 olur.
   - `fuel_dryness` ters sıralanır: düşük NDMI daha kuru demektir.
2. **NaN politikası:**
   - `all_water` olan `187664557_0019` segmenti kuruluk için 0 alır; segment düşük kademede (skor 24,5).
   - Belgelenmiş diğer nedenler nötr 0,5 alır ve `imputed` sütununda işaretlenir. Pilotta böyle bir segment yok.
   - `asset_condition` için veri yok ve ağırlığı 0; skora girmiyor. Ağırlığı 0'dan büyük yapılırsa skor hata verir.
3. **Bileşenler:**
   - `P = Σ w_i·f_i` (ignition), `C = Σ w_j·f_j` (consequence).
   - Ağırlıklar bileşen toplamına bölünür. Config toplamları 1 olduğu için uyarı yok.
4. **Birleştirme:** `risk = 100·sqrt(P·C)` (config `combine: geometric`).
5. **Katkı:** `contrib_<faktör>`, referans segmente (tüm faktörler 0,5, risk 50) göre tam Shapley değeridir; 8 faktör için 256 koalisyon hesaplanır.
   - top_factors, katkısı pozitif olan en büyük en fazla 3 faktördür. Biçim: `{key, label_tr, label_en, contribution}`.
   - Katkısı pozitif faktör sayısı 3'ten az olabilir. Pilotta 925 segmentin 812'sinde 3, 87'sinde 2, 21'inde 1, 5'inde 0 faktör var.
6. **Kademe:** Riskin orta-sıra AOI yüzdeliği ≥ 0,95 ise kritik, ≥ 0,80 ise yüksek, ≥ 0,50 ise orta, altı düşük. Bağlı segmentler aynı kademede kalır.
7. **İş paketi:** Kritik/yüksek segmentler yalnız aynı hat, ardışık `seq` ve uç uca değme (≤ 1 m) koşullarıyla birleşir.
   - İlçe sınırı yüzünden bölünmüş hat parçaları birleşmez. Pilotta 6 boşluk var (12,7 m – 12,3 km); hiçbir açıklık bunların üstünden geçmiyor.
   - Sıralama: risk_max ↓, strike_tree_count ↓, span_id ↑.

### Katkı yönteminin gerekçesi (kritik + yüksek, n = 185)
| as_of | yöntem | 1. neden dağılımı | 1. nedenin yüzdelik medyanı | 1. nedeni yüzdelik < 0,6 |
|---|---|---|---|---|
| 2025-05-31 | pay bölüşümü (w·f, P ve C yarı yarıya) | fuel_continuity 114, vegetation_encroachment 48, wui_exposure 22, slope 1 | 0,85 | %6 |
| 2025-05-31 | **Shapley (seçilen)** | vegetation_encroachment 78, fuel_continuity 71, wui_exposure 15, strike_trees 12, slope 5, fuel_dryness 3, wind_exposure 1 | 0,91 | %0 |
| 2026-10-30 | pay bölüşümü | fuel_continuity 106, vegetation_encroachment 51, wui_exposure 27, slope 1 | 0,86 | %6 |
| 2026-10-30 | **Shapley (seçilen)** | vegetation_encroachment 84, fuel_continuity 58, wui_exposure 17, strike_trees 11, fuel_dryness 7, slope 5, wind_exposure 3 | 0,92 | %0 |

Pay bölüşümü, en ağır ağırlığı (fuel_continuity 0,40) neredeyse her segmentte birinci neden yapıyor; faktör o segmentte sıradan olsa bile. Shapley ise segmenti tipik segmentten ayıran faktörü öne çıkarıyor.

## Çıktı şemaları (`data/processed/izmir_menderes/`)
| dosya | içerik |
|---|---|
| `risk_<as_of>.parquet` | GeoParquet, EPSG:4326, 925 satır, segments.parquet sırası. Metaveri `hatkalkani_risk` anahtarında; okuma: `hatkalkani.model.run.read_risk(path)` |
| `risk_<as_of>.meta.json` | Okunabilir metaveri eşi (aşağıda) |
| `risk_<as_of>.geojson` | Arayüz katmanı (571 KB): `/api/segments` özellikleri; top_factors gerçek dizi; risk 1, P ve C 3 ondalık; koordinatlar 6 ondalık; RFC 7946 |
| `workorders_<as_of>.csv` | UTF-8 BOM, virgül ayraçlı, CRLF; geometri yok |
| `workorders_<as_of>.geojson` / `.gpkg` | Aynı alanlar + açıklık LineString'i; EPSG:4326; GPKG katmanı `workorders` |

**risk parquet sütunları:**
- Kimlik ve hat: `segment_id, line_id, seq, voltage_class, voltage_level, voltage_kv, length_m, as_of`.
- Skor: `risk, risk_pct, tier, p_ignition, consequence`.
- Faktör başına: `norm_<f>`, `contrib_<f>`, `raw_<f>`.
- Diğer: `imputed`, `top_factors` (JSON metni), `aux_strike_tall_clusters`, `chm_year` (null; CHM v2 tarihsiz, ADR-008), `geometry`.

**Metaveri:**
- Config anlık görüntüsü ve `weights_effective`.
- NaN politikası ve `imputed_counts`.
- Referans (0,5 → 50).
- Kademe sayıları.
- Skor, P ve C özetleri.
- İş paketi tanımları.
- Girdi SHA-256'ları: features, segments, risk_weights.yaml.

**İş paketi alanları:**
- Spec §4'teki alanların tamamı: `span_id, line_id, voltage_class, length_m, risk_max, risk_mean, main_reason_tr, strike_tree_count, start_lat, start_lon, end_lat, end_lon, map_url`.
- Ek alanlar: `priority, tier_max, n_segments, segment_ids, voltage_level, voltage_kv, main_reason_key, main_reason_en, reasons_tr, reasons_en, strike_tall_count, as_of`.

## Kademe dağılımı
| kademe | segment | pay | risk aralığı 2025-05-31 | km 2025-05-31 | risk aralığı 2026-10-30 | km 2026-10-30 |
|---|---|---|---|---|---|---|
| kritik | 46 | %5,0 | 65,5 – 79,0 | 4,6 | 65,3 – 77,7 | 4,6 |
| yuksek | 139 | %15,0 | 59,2 – 65,4 | 13,9 | 58,8 – 65,2 | 13,8 |
| orta | 278 | %30,1 | 48,7 – 59,2 | 27,7 | 49,0 – 58,8 | 27,8 |
| dusuk | 462 | %49,9 | 16,5 – 48,7 | 46,3 | 19,0 – 49,0 | 46,2 |

## Skor dağılımı
| as_of | alan | ort | std | min | p10 | p25 | p50 | p75 | p90 | p95 | max |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-05-31 | risk | 49,1 | 10,9 | 16,5 | 35,3 | 41,8 | 48,7 | 57,7 | 62,8 | 65,4 | 79,0 |
| 2025-05-31 | P | 0,500 | 0,151 | 0,139 | 0,304 | 0,400 | 0,484 | 0,609 | 0,694 | 0,752 | 0,965 |
| 2025-05-31 | C | 0,500 | 0,121 | 0,098 | 0,341 | 0,422 | 0,510 | 0,600 | 0,641 | 0,662 | 0,785 |
| 2026-10-30 | risk | 49,1 | 10,5 | 19,0 | 35,7 | 41,8 | 49,0 | 57,3 | 62,5 | 65,2 | 77,7 |
| 2026-10-30 | P | 0,500 | 0,148 | 0,139 | 0,311 | 0,390 | 0,486 | 0,609 | 0,696 | 0,742 | 0,956 |
| 2026-10-30 | C | 0,500 | 0,121 | 0,097 | 0,340 | 0,422 | 0,510 | 0,600 | 0,641 | 0,662 | 0,783 |

- **C'nin aralığı:** F3-1'in "C dar toplanabilir" uyarısı kısmen doğrulandı. C'nin standart sapması P'ninkinden düşük (0,121'e karşı 0,151) ve üst ucu 0,79'da kalıyor. Bunun nedeni, `wui_exposure`'ın `fuel_continuity` ve `slope` ile ters yönde ilerlemesi (ρ −0,63).
- **wui_exposure'ın katkısı:** Kritik segmentlerde ortalama katkısı negatif (−0,5 puan). Model ormanlık ve dik koridorları öne çıkarıyor; bu koridorlar yerleşimden uzak.

## top_factors örnekleri
| as_of | segment | kademe | risk | P | C | top_factors (puan, tipik segmente göre) |
|---|---|---|---|---|---|---|
| 2025-05-31 | 187664557_0012 | kritik | 79,0 | 0,952 | 0,655 | Hatta yakın yüksek ağaç +7,5; Kuru bitki örtüsü +5,4; Hatta devrilebilecek ağaç +5,2 |
| 2025-05-31 | 1181165604_0007 | yuksek | 61,8 | 0,576 | 0,663 | Hatta yakın yüksek ağaç +8,6; Kesintisiz orman/maki +8,2; Dik yamaç +3,7 |
| 2025-05-31 | 183275602_0029 | dusuk | 16,5 | 0,207 | 0,131 | Geçmiş yangın yoğunluğu +1,6; Rüzgâra açıklık +0,2 |
| 2026-10-30 | 187664557_0012 | kritik | 77,7 | 0,922 | 0,655 | Hatta yakın yüksek ağaç +7,5; Hatta devrilebilecek ağaç +5,2; Kuru bitki örtüsü +4,1 |
| 2026-10-30 | 1181164690_0083 | yuksek | 61,2 | 0,580 | 0,647 | Hatta yakın yüksek ağaç +8,4; Kesintisiz orman/maki +5,5; Dik yamaç +4,5 |
| 2026-10-30 | 183275602_0040 | dusuk | 19,0 | 0,350 | 0,103 | Geçmiş yangın yoğunluğu +1,9; Kuru bitki örtüsü +1,1 |

**1. neden, kademeye göre** (2025-05-31; güncel haritada dağılım benzer):

| kademe | enc | strike | dryness | wind | fuel | wui | slope | fire | (yok) |
|---|---|---|---|---|---|---|---|---|---|
| kritik | 29 | 2 | 1 | 1 | 11 | 1 | 1 | 0 | 0 |
| yuksek | 50 | 10 | 2 | 0 | 59 | 14 | 4 | 0 | 0 |
| orta | 71 | 23 | 15 | 6 | 92 | 55 | 14 | 2 | 0 |
| dusuk | 17 | 14 | 83 | 28 | 84 | 183 | 36 | 12 | 5 |

**Ortalama katkı (puan), kademeye göre** (2025-05-31):

| kademe | enc | strike | dryness | wind | fuel | wui | slope | fire |
|---|---|---|---|---|---|---|---|---|
| kritik | 5,9 | 4,0 | 1,8 | 1,6 | 3,4 | −0,5 | 2,6 | 1,2 |
| yuksek | 4,8 | 3,2 | −1,1 | 0,4 | 4,2 | −1,2 | 1,9 | −0,1 |
| orta | 2,0 | 1,6 | −0,9 | −0,5 | 1,6 | −0,5 | 0,8 | −0,1 |
| dusuk | −3,6 | −2,6 | 0,3 | −0,1 | −3,1 | 0,8 | −1,5 | 0,0 |

## İş paketleri
| as_of | açıklık | toplam km | segment | uzunluk p50 / max (m) | kritik içeren | tek segmentlik |
|---|---|---|---|---|---|---|
| 2025-05-31 | 72 | 18,5 | 185 | 100 / 1600 | 17 | 38 |
| 2026-10-30 | 76 | 18,4 | 185 | 100 / 1700 | 16 | 45 |

**Ana neden dağılımı (açıklık sayısı):**
- 2025-05-31: Hatta yakın yüksek ağaç 29 · Kesintisiz orman/maki 26 · Yerleşime yakınlık 11 · Hatta devrilebilecek ağaç 3 · Dik yamaç 2 · Kuru bitki örtüsü 1.
- 2026-10-30: 28 · 24 · 14 · 3 · Kuru bitki örtüsü 3 · Dik yamaç 2 · Rüzgâra açıklık 2.

**3 örnek iş paketi** (güncel harita, 2026-10-30; öncelik sırası, kesin bakım kararı değil):

| öncelik | span_id | gerilim | uzunluk (m) | risk_max | risk_mean | ana neden | strike_tree_count | başlangıç (lat, lon) | bitiş (lat, lon) | map_url |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 187664557_0001-0017 | ge154kv | 1700 | 77,71 | 70,90 | Hatta yakın yüksek ağaç | 93 | 38.147961, 27.076541 | 38.137183, 27.089820 | https://www.google.com/maps?q=38.142451,27.082886 |
| 2 | 1181160379_0028-0031 | etiketsiz | 400 | 73,51 | 67,95 | Kesintisiz orman/maki | 14 | 38.161727, 27.063813 | 38.164305, 27.060632 | https://www.google.com/maps?q=38.163075,27.062297 |
| 3 | 1181160379_0111-0118 | etiketsiz | 800 | 72,09 | 65,91 | Hatta yakın yüksek ağaç | 38 | 38.203424, 26.986694 | 38.206143, 26.978231 | https://www.google.com/maps?q=38.204782,26.982462 |

Backtest haritasında ilk üç sıra:
1. 187664557_0002-0017: 1600 m, risk_max 78,97, Hatta yakın yüksek ağaç.
2. 1181160379_0028-0031: 400 m, 76,65, Kesintisiz orman/maki.
3. 1181165604_0001-0007: 700 m, 75,96, Kesintisiz orman/maki.

**Okuma notları:**
- `strike_tree_count`, açıklıktaki segmentlerin `strike_trees` küme sayılarının toplamıdır. Komşu iki segmentin sınırındaki bir küme iki kez sayılabilir. Ayrıca kümelerin %34'ü 4 m'nin altındaki çalılıktır (O8). 4 m ve üstü kümelerin sayısı `strike_tall_count` alanında ayrıca veriliyor.
- 1,7 km'lik açıklık tek bir iş paketi için uzun olabilir. Bölme kuralı (örneğin en fazla N segment) saha geri bildirimiyle config'e eklenebilir.

## ±%20 ağırlık duyarlılığı
- **Varyantlar:** Her varyantta tek bir ağırlık ×0,8 ya da ×1,2 yapıldı ve bileşen içinde yeniden normalize edildi. Skorlar bellekte hesaplandı; config değişmedi.
- **Örtüşme tanımı:** Üst-%20 kümesi kritik + yüksek segmentlerdir, üst-%5 kümesi kritik segmentlerdir. Örtüşme = |A ∩ B| / |A|.

| varyant | Spearman 2025 | üst-%20 2025 | üst-%5 2025 | Spearman 2026 | üst-%20 2026 | üst-%5 2026 | C std 2025 |
|---|---|---|---|---|---|---|---|
| vegetation_encroachment ×0,8 / ×1,2 | 0,998 / 0,999 | 0,973 / 0,973 | 0,978 / 0,957 | 0,998 / 0,999 | 0,957 / 0,968 | 0,957 / 0,957 | 0,121 |
| strike_trees ×0,8 / ×1,2 | 0,998 / 0,999 | 0,962 / 0,989 | 0,978 / 0,957 | 0,998 / 0,999 | 0,973 / 0,973 | 0,935 / 0,978 | 0,121 |
| fuel_dryness ×0,8 / ×1,2 | 0,998 / 0,998 | 0,968 / 0,973 | 0,913 / 0,957 | 0,998 / 0,998 | 0,962 / 0,968 | 0,957 / 0,935 | 0,121 |
| wind_exposure ×0,8 / ×1,2 | 0,999 / 0,999 | 0,984 / 0,957 | 0,913 / 0,935 | 0,999 / 0,999 | 0,951 / 0,957 | 0,978 / 0,978 | 0,121 |
| fuel_continuity ×0,8 / ×1,2 | 0,996 / 0,998 | 0,951 / 0,962 | 0,913 / 0,913 | 0,996 / 0,997 | 0,935 / 0,962 | 0,935 / 0,913 | 0,112 / 0,130 |
| wui_exposure ×0,8 / ×1,2 | 0,995 / 0,996 | 0,946 / 0,957 | 0,913 / 0,935 | 0,995 / 0,996 | 0,946 / 0,941 | 0,935 / 0,935 | 0,133 / 0,112 |
| slope ×0,8 / ×1,2 | 0,999 / 0,999 | 0,968 / 0,978 | 0,935 / 0,935 | 0,999 / 0,999 | 0,968 / 0,973 | 0,978 / 0,957 | 0,117 / 0,125 |
| fire_history ×0,8 / ×1,2 | 1,000 / 1,000 | 0,984 / 0,978 | 1,000 / 0,935 | 1,000 / 1,000 | 0,978 / 0,968 | 0,978 / 0,978 | 0,123 / 0,119 |
| combine: linear | 0,987 | 0,924 | 0,848 | 0,984 | 0,876 | 0,804 | 0,121 |

**Okuma notları:**
- **Sıralama sağlam:** Tek bir ağırlığın ±%20 değişmesi, sıralamayı neredeyse hiç değiştirmiyor (ρ ≥ 0,995). Kritik kümede (46 segment) en çok 4 segment el değiştiriyor (örtüşme 0,913 = 42/46).
- **En hassas ağırlıklar:** C'deki `fuel_continuity` ve `wui_exposure`. Bu iki faktör birbirine ters çalıştığı için C'nin dağılımını en çok onlar değiştiriyor (C std 0,112–0,134).
- **Birleştirme biçimi:** Geometrik yerine doğrusal birleştirme, herhangi bir tek ağırlıktan daha büyük bir etki yaratıyor (üst-%5 örtüşmesi 0,80–0,85). Hangisinin daha iyi olduğu ancak F3-3'teki lift karşılaştırmasıyla söylenebilir.

## İki as_of arasındaki fark
- Spearman(risk) = 0,953.
- Üst-%20 örtüşmesi 0,859, üst-%5 örtüşmesi 0,696.

| 2025-05-31 \ 2026-10-30 | kritik | yuksek | orta | dusuk |
|---|---|---|---|---|
| kritik | 32 | 14 | 0 | 0 |
| yuksek | 12 | 101 | 26 | 0 |
| orta | 2 | 24 | 222 | 30 |
| dusuk | 0 | 0 | 30 | 432 |

- **Farkın kaynağı:** Fark yalnız zamana bağlı iki faktörden geliyor.
  - `fuel_dryness`: bahar ile sonbahar kompozitleri arasında ρ 0,51 (F3-1).
  - `fire_history`: 2025 sezonu güncel haritada geçmişe giriyor.

  Statik faktörler iki tarihte aynı.
- **Kritik kümedeki değişim:** Kritik segmentlerin üçte biri öbür tarihte yüksek kademeye geçiyor. Bu yüzden backtest'te doğrulanan sıralama, güncel haritadakiyle birebir aynı değil.

## Zaman sızıntısı (skor düzeyi)
`tests/model/test_score_leakage.py` dosyasındaki testler sentetik AOI üzerinde uçtan uca çalışıyor: ingest dosyası → features → skor → iş paketi.

- **Negatif test:** Her segmente kesimde ve sonrasında VIIRS tespitleri (NRT dahil) eklendi. Kesim sonrası tüm rüzgâr saatleri 99 m/s yapıldı. Penceresi as_of'tan sonra biten bir S2 kompoziti eklendi. Sonuçta `risk, risk_pct, tier, p_ignition, consequence, top_factors, contrib_*, norm_*` ve iş paketi tablosu `assert_frame_equal` ile birebir aynı.
- **Pozitif kontrol:** 2024 Temmuz'unda (kesimden önce) 6 ayrı günde `1001_0003` orta noktasına tespit eklendi. Bu segmentin `norm_fire_history` değeri ve skoru artıyor.

## Diğer testler
- `test_score.py` (12 test):
  - kaba kuvvetle hesaplanan yüzdelik ve P/C/risk formülü (geometrik ve doğrusal),
  - NaN politikası,
  - unavailable faktörün ağırlık taşıyamaması,
  - ağırlıkların yeniden normalize edilmesi,
  - **config'teki ağırlık değişince skorun değişmesi**,
  - yeni faktörün tek sütun + meta + ağırlıkla eklenmesi,
  - kademe oranları (n = 1000 → 50/150/300/500),
  - bağların aynı kademede kalması,
  - geçersiz config,
  - tekrarlanabilirlik.
- `test_explain.py` (7 test):
  - Hızlı Shapley, tüm permütasyonlar üzerinden hesaplanan tanımla aynı sonucu veriyor (geometrik ve doğrusal).
  - Verimlilik: katkılar toplamı = risk − 50.
  - Doğrusal birleştirmede kapalı biçimle aynı sonuç.
  - Boş ve simetrik oyuncular.
  - top_factors'ta sıra, işaret ve eşitlik kuralı.
- `test_workorders.py` (5 test): yalnız ardışık ve bitişik segmentlerin birleşmesi (40 m boşluk birleşmiyor), alan değerleri, koordinatlar, map_url, sıralama, boş tablo ve CRS'siz girdinin reddi.
- `test_model_cli.py` (5 test):
  - Sentetik AOI'de tüm dosyalar EPSG:4326'da üretiliyor.
  - İkinci çalıştırmada dosyalar bayt bayt aynı.
  - Özellik dosyası yoksa açık bir hata veriyor.
  - `--stage score` komutu doğru kuruluyor ve `all` içinde çalışıyor.
  - Config'teki ağırlık değişince CLI skoru da değişiyor.
- `test_risk_real_outputs.py` (4 test): Pilot dosyalarında kontrol edilenler:
  - 925 satır, segment sırası,
  - katkılar toplamı = risk − 50,
  - kademe sayıları, bağımsız yüzdelik hesabıyla karşılaştırılıyor,
  - GeoJSON özellikleri,
  - CSV'de BOM ve sütunlar,
  - GPKG'nin CRS'i,
  - her kritik/yüksek segmentin tam bir açıklıkta yer alması.
- `tests/export/test_export_files.py` (4 test): CSV'de BOM, Türkçe karakter, tırnaklı URL ve CRLF; GeoJSON'un RFC 7946'ya uygunluğu ve iç içe özellikleri; GPKG'nin EPSG:4326'da gidiş-dönüşü ve dosyanın üstüne yazılması.

## Sınırlamalar ve riskler
1. **Doğrulama yok:** Lift, güven aralığı, olay sayısı ve taban çizgileri F3-3'te hesaplanacak. Bu skorların FIRMS olaylarını rastgeleden iyi sıraladığı henüz gösterilmedi.
2. **Kademeler görelidir:** Her AOI'de ve her as_of'ta %5 kritik çıkar. "Kritik", ilçenin en yüksek %5'lik dilimi demektir; mutlak bir tehlike düzeyi değildir.
3. **wind_exposure fiilen topoğrafyadır (ρ 0,98, F3-1):** Etiketi "Rüzgâra açıklık" olduğu için gerçek rüzgârı ölçüyormuş gibi okunabilir. Kritik segmentlerde 1. neden olarak yalnız 1 kez çıkıyor; etkisi küçük.
4. **Güncel harita geçicidir:** FIRMS uzatması bitince `features_2026-10-30` yeniden üretilmeli ve `--stage score` yeniden çalıştırılmalı (2,9 sn). Şu anki dosyada 2025-10-01 – 2026-10-30 arasındaki yangınlar yok.
5. **Statik girdilerin bilinen sorunları skora da taşınıyor:**
   - CHM taban yılı bilinmiyor (`chm_year` null).
   - Açıklık bantları yer tutucu (`placeholder_unverified`).
   - strike_trees çalıyı da sayıyor (O8).
   - OSM hatlarının çoğu iletim hattı (ADR-007).

## Öneriler (config değişikliği gerektirir; orkestratör onayı)
- **`labels.wind_exposure.tr`:** "Rüzgâra topoğrafik açıklık" olarak değiştirilmeli. Etiket config'ten okunduğu için özellikleri yeniden üretmek gerekmez; yalnız `--stage score` çalıştırılır.
- **Config'e taşınacak sabitler:**
  - `nan_fill` (all_water → 0, diğer → 0,5),
  - `reference_percentile` (0,5),
  - `top_factors_n` (3),
  - `contiguity_tolerance_m` (1 m),
  - isteğe bağlı `max_span_segments` (açıklık bölme).
- **Birleştirme ve O8 karşılaştırması (F3-3'te):** `combine: geometric` ile `linear`'ın lift'i, ayrıca `strike_trees` ile `aux_strike_tall_clusters` tanımları karşılaştırılmalı. Bu bölümdeki duyarlılık tablosu, birleştirme biçiminin ağırlık ayarından daha etkili olduğunu gösteriyor.
- **C bileşeni:** `wui_exposure` ile yakıt sürekliliği birbirine ters çalışıyor. Saha geri bildirimine göre "sonuç"un ayrı iki eksen olarak gösterilmesi düşünülebilir: yangın yayılımı ve yerleşime etki.

## Backend ve arayüz için notlar
- **Dosya adları:** `risk_<as_of>.*` ve `workorders_<as_of>.*`. Güncel harita için as_of değeri config'teki `periods.current_asof`'tur.
- **API'ye hazır dosyalar:**
  - `risk_<as_of>.geojson`, `/api/segments` sözleşmesindeki alanların tamamını taşıyor.
  - `/api/segments/{id}` için `raw_*`, `contrib_*`, `norm_*` ve `chm_year` parquet'te.
- **top_factors uzunluğu:** Liste 0–3 öğe içerebilir. Boş listede arayüz "belirgin bir yükseltici neden yok" yazmalı.
- **Katkı değeri:** `contribution` alanı "tipik segmente göre puan" anlamına gelir; arayüzde "+7,5 puan" biçiminde gösterilmeli.
- **Gerilim alanları:** `voltage_class` değerleri ge154kv/etiketsiz… biçimindedir; lv/mv/hv sınıfı `voltage_level` alanında.
- **CSV ayracı:** CSV'de ayraç virgüldür. Türkçe yerel ayarlı Excel'de dosya "Veri > Metinden/CSV'den" ile açılmalı. Gerekirse `hatkalkani.export.write_csv(..., sep=";")` kullanılabilir.

## Değişen ve eklenen dosyalar
- **Paket `src/hatkalkani/model/`:** `config.py`, `normalize.py`, `explain.py`, `score.py`, `workorders.py`, `run.py`.
- **Paket `src/hatkalkani/export/`:** `writers.py`, `__init__.py`.
- **`scripts/run_pipeline.py`:** `--stage score` eklendi; `all` artık score'u da çalıştırıyor. ingest ve features yolları değişmedi.
- **Testler:**
  - `tests/model/`: `conftest.py`, `model_synth.py`, `test_score.py`, `test_explain.py`, `test_workorders.py`, `test_score_leakage.py`, `test_model_cli.py`, `test_risk_real_outputs.py`; `test_model_package.py` yalnız docstring.
  - `tests/export/test_export_files.py`.
  - `tests/features/synth.py`: sentetik config'e `tiers` eklendi.
  - `tests/features/test_pipeline_features.py`: `all` aşamasının beklentisine score eklendi.
- **Not defteri:** `notebooks/f3_2_score_summary.py`.
- **Veri:** `data/processed/izmir_menderes/risk_<as_of>.{parquet,meta.json,geojson}` ve `workorders_<as_of>.{csv,geojson,gpkg}`; iki as_of için.
- **`docs/DECISIONS.md`:** ADR-010.
- **Dokunulmayanlar:** `src/hatkalkani/ingest/` ve `features/` paketlerine dokunulmadı.

## Doğrulama komutları
| komut | sonuç |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run pytest tests/features tests/model -q` | 104 passed (`tests/export`: 4 passed) |
| `uv run pytest -q` | 162 passed, 2 deselected (ağ), 1 uyarı (`ingest/chm.py`, F3-2 dışı) |
| `uv run python scripts/run_pipeline.py --aoi izmir_menderes --stage score` | rc 0; iki as_of için 3,0 sn (duvar saati, uv başlangıcı dahil); tepe bellek 188 MB; yeniden çalıştırmada 10 dosyanın SHA-256 değeri aynı |

Not: Proje `addopts` ayarı zaten `-q` içerdiği için `uv run pytest -q` özet satırı basmaz; sayılar `-o addopts="-m 'not network'"` ile alındı.
