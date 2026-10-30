---
name: risk-model-spec
description: HatKalkanı risk modeli tanımı. Hat segmentasyonu, faktörler, skor birleştirme, kademeler, açıklanabilirlik, iş paketleri, geriye dönük test protokolü ve önleyici kesinti senaryosu. Risk modeli kuran veya inceleyen alt ajanlara önceden yüklenir.
user-invocable: false
---

# Risk modeli tanımı (v0.1)
Bu modeli risk-modeler geliştirir. Değişiklikler docs/DECISIONS.md'ye ADR olarak yazılır.

Parametrelerin yeri:
- Mesafe ve tamponlar: config/aoi.yaml → `buffers_m.*`
- Segmentasyon: config/aoi.yaml → `segmentation.*`
- Dönemler: config/aoi.yaml → `periods.*`
- Ağırlıklar ve model parametreleri: config/risk_weights.yaml → `ignition`, `consequence`, `parameters`, `tiers`, `scenario`

## İlkeler
- **Öncelik, tespit değil:** Çıktı bir öncelik sırasıdır, kesin tespit değildir. Arayüzde ve dokümanlarda "olası" ve "öncelik" dili kullanılır.
- **Kural tabanlı v0.1:** Etiketli tutuşma verisi olmadığı için v0.1 kural tabanlıdır ve config/risk_weights.yaml ile ayarlanır. ML ancak pilot şirket verisiyle gelir.
- **Açıklanabilirlik:** Her skor açıklanabilir olmalı; her parça için faktör katkıları saklanır.
- **Zaman sızıntısı yasak:** `as_of` tarihinden sonraki hiçbir veri özelliklere giremez (özellikle FIRMS geçmişi, Sentinel-2 ve rüzgâr klimatolojisi).

## 1. Hatlar ve segmentasyon
- **Kaynak:** OSM `power=line` ve `power=minor_line`. Yer altı `power=cable` hariçtir. Hatlar AOI ile kırpılır.
- **Gerilim sınıfı:** `voltage` etiketinden (V cinsinden) çıkarılır:

  | Etiket | Sınıf |
  |---|---|
  | < 1000 | `lv` |
  | 1000–36000 | `mv` |
  | > 36000 | `hv` |
  | yok, `minor_line` | `mv` |
  | yok, `line` | `hv` |

  Kaynağı `voltage_source` alanına yaz: `tag` veya `assumed`.
- **Bölme:** Metrik CRS'de hattı ~`segmentation.segment_length_m` uzunluğunda parçalara böl. Son parça `segmentation.min_last_segment_m`'den kısaysa önceki parçaya ekle.
- **Kimlikler:** `segment_id = f"{osm_way_id}_{i:04d}"`, `line_id = osm_way_id`.

## 2. Özellikler (features.parquet)
Her faktörün ham değeri normalize edilmeden ayrı bir sütunda saklanır.

| Faktör | Ham tanım | Veri |
|---|---|---|
| vegetation_encroachment | Açıklık bandındaki (gerilim sınıfına göre `clearance_band_m`) CHM piksellerinden yüksekliği ≥ `min_encroach_canopy_m` olanların oranı | CHM, hat |
| strike_trees | ±`strike_max_distance_m` koridorunda h ≥ d + `strike_margin_m` koşulunu sağlayan bağlı piksel kümelerinin (≥4 px) sayısı. d: hatta yatay uzaklık | CHM |
| fuel_dryness | Koridordaki (±`buffers_m.dryness`) NDMI medyanının AOI içi ters yüzdeliği. Düşük NDMI kuru demektir | Sentinel-2 |
| wind_exposure | `periods.wind_climatology_summers` yıllarında (Haz–Eyl) saatlik rüzgâr hamlesi 95. yüzdeliği × topoğrafik açıklık çarpanı (TPI'den, 0,5–1,5) | Open-Meteo, DEM |
| fuel_continuity | `buffers_m.fuel` tamponunda WorldCover ağaç (10) + çalılık (20) oranı | WorldCover |
| slope | Koridorda (±`buffers_m.slope`) ortalama eğim (°) | DEM |
| wui_exposure | `buffers_m.wui` içindeki bina sayısı, log1p | Overture/OSM |
| fire_history | as_of'tan önceki FIRMS tespitlerinin `buffers_m.history_kernel` çekirdek yoğunluğu | FIRMS |
| asset_condition | Direk yaşı, iletken tipi (pilotta şirket verisinden) | yok; demoda ağırlık 0 |

Notlar:
- **CHM:** Taban yılı karodan karoya farklıdır; MODEL_CARD'da yaz. MAE ~2,8 m olduğundan tek piksele değil kümelere bak.
- **fire_history:** Zayıf bir önseldir; tarım yakmaları gürültü katar. Ağırlığı küçük tut.

## 3. Skor
- **Normalizasyon:** Her faktör AOI içi yüzdelik sıraya çevrilir (0–1). config: `normalization`.
- **Bileşenler:**
  - Tutuşma olasılığı: `P = Σ w_i·f_i` (ignition ağırlıkları)
  - Sonuç: `C = Σ w_j·f_j` (consequence ağırlıkları)
- **Birleştirme:**
  - `combine: geometric` → `risk = 100·sqrt(P·C)` (varsayılan; olasılık ve sonuç birlikte gerekir)
  - `combine: linear` → `risk = 100·(0.6·P + 0.4·C)` (duyarlılık karşılaştırması için)
- **Kademeler:** AOI içi yüzdelik eşiklerle (`tiers`): `kritik`, `yuksek`, `orta`, `dusuk`.
- **Çıktı alanları:** `risk`, `tier`, `p_ignition`, `consequence`, `contrib_<faktör>`, `top_factors`. top_factors, en çok katkı veren 3 faktördür; anahtarı, Türkçe ve İngilizce etiketi ile katkısı yazılır.
- **Faktör kaydı:** `FACTORS = {ad: fonksiyon}` gibi bir kayıt kullan. Yeni faktör = bir fonksiyon + config'te bir ağırlık satırı.

## 4. İş paketleri (budama/drone listesi)
- **Birleştirme:** Aynı hatta ardışık `kritik` ve `yuksek` parçaları birleştirerek açıklıklar (span) oluştur.
- **Alanlar:**
  - `span_id`, `line_id`, `voltage_class`, `length_m`
  - `risk_max`, `risk_mean`, `main_reason_tr`, `strike_tree_count`
  - `start_lat`, `start_lon`, `end_lat`, `end_lon` (WGS84)
  - `map_url` (`https://www.google.com/maps?q=<lat>,<lon>`)
- **Sıralama:** risk_max azalan; eşitlikte strike_tree_count azalan.
- **Dışa aktarım:** CSV (UTF-8 BOM), GeoJSON ve GeoPackage.

## 5. Geriye dönük test (dürüst değerlendirme)
- **as_of = config `periods.backtest_asof`:** Özellikler yalnızca bu tarihe kadar olan veriyle hesaplanır.
- **Olaylar:**
  - Kaynak: `periods.backtest_season` içindeki FIRMS VIIRS tespitleri.
  - Kümeleme: uzay-zamanda kümelenir (~1 km, 2 gün). Kümenin ilk tespiti tutuşma vekilidir.
  - Hatta ≤`buffers_m.event_line_distance` uzaklıktaki kümeler "hat yakını olay" sayılır.
- **Metrikler:**
  - Her hat yakını olay için en yakın parçanın risk yüzdeliği.
  - Üst %10 ve üst %20'ye düşen olay payı.
  - `lift = pay / beklenen pay`.
  - Bootstrap ile %95 güven aralığı. Olay sayısı küçükse bunu açıkça yaz.
- **Taban çizgileri:**
  - (a) rastgele
  - (b) yalnızca ağaç/çalı örtüsü
  - (c) yalnızca bina yakınlığı

  Model bunları geçmiyorsa bunu raporla.
- **Vaka incelemeleri:** Belgelenmiş 2025 vakaları için (docs/reports/F1-3) konum belirsizliğiyle birlikte sıra yüzdeliği ver.
- **Sınırlar (MODEL_CARD.md'ye yaz):**
  - FIRMS pikseli ~375 m'dir.
  - Tespit, tutuşma noktası değildir.
  - Nedeni bilinmeyen yangınlar da olaylara dahildir.
  - Tarım yakmaları gürültü katar.

## 6. Önleyici kesinti senaryosu
- **Girdi:** tarih (geçmiş gün veya tahmin), `gust_threshold_kmh`, `risk_threshold_tier`.
- **Kesinti adayı:** O gün saatlik rüzgâr hamlesinin maksimumu eşiği aşan VE kademesi eşik ya da üstünde olan parçalar.
- **Kesinti birimi:** Aday parça içeren OSM hat yolu (way) bir vekildir. Gerçek şebekede anahtarlanabilir bölüm veya fider bilgisi gerekir; arayüzde "vekil" diye belirt.
- **Karşılaştırma:**
  - (A) İlçe geneli: AOI'deki tüm havai hatlar kesilir.
  - (B) Hedefli: yalnızca adaylar kesilir.

  Metrikler:
  - Kesilen hat km'si.
  - Kesilen hatlara ≤`buffers_m.affected_building` uzaklıktaki bina sayısı (etkilenen yapı vekili).
  - B'nin kapsadığı toplam riskin A'ya oranı.
- **Duyarlılık:** Eşiği ±10 km/s değiştirerek sonuç tablosu ver.
- **Senaryo günü:** config `demo.scenario_date_candidates` içinden en rüzgârlı gün seçilir; seçim DECISIONS.md'ye yazılır.

## 7. Çıktılar
- `data/processed/<aoi>/` altında:
  - `segments.parquet`, `features.parquet`, `risk.parquet`
  - `risk.geojson` (arayüz için sadeleştirilmiş)
  - `workorders.csv`, `workorders.geojson`, `workorders.gpkg`
  - `backtest.json`, `events_<sezon>.geojson`
  - `scenario_<tarih>.json`, `scenario_dates.json`
- Model kartı: `docs/MODEL_CARD.md`.

## 8. Kabul kriterleri
- Pipeline pilot ilçede önbellekteki veriyle ≤30 dk'da çalışır.
- Skor tekrarlanabilirdir: aynı girdi aynı çıktıyı verir.
- Şunlar için testler vardır:
  - segment uzunlukları
  - CRS dönüşümleri
  - as_of sızıntısı
  - kademe oranları
  - iş paketi birleştirme
  - senaryo karşılaştırması
