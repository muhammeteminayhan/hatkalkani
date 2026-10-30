# Mimari

## Veri akışı
```
Açık veri (OSM, Meta/WRI CHM, Sentinel-2, DEM, WorldCover, Overture, Open-Meteo, FIRMS)
   │  src/hatkalkani/ingest        (data-engineer)
   ▼
data/raw/<kaynak>/ + MANIFEST.csv  →  data/interim/<aoi>/
   │  src/hatkalkani/features      (risk-modeler)  as_of parametreli
   ▼
features.parquet
   │  src/hatkalkani/model         (risk-modeler)  skor · iş paketleri · geriye dönük test · senaryo
   ▼
data/processed/<aoi>/  (risk.parquet, risk.geojson, workorders.*, backtest.json, scenario_*.json)
   │  src/hatkalkani/api + export  (backend-dev)   FastAPI, ağ çağrısı yok
   ▼
web/  (frontend-dev)  tek sayfa, MapLibre GL JS, derleme adımı yok
```

## Komutlar (hedef)
- `uv run python scripts/run_pipeline.py --aoi <id> --stage all|ingest|features|model|backtest|scenario`
- `uv run python scripts/serve.py` → http://127.0.0.1:8000
- `uv run pytest`

## API sözleşmesi (v0.1)
Tüm yanıtlar JSON (UTF-8) ve koordinatlar EPSG:4326'dır. Sözleşme değişikliği DECISIONS.md'ye yazılır; backend ve frontend aynı anda güncellenir.

| Uç nokta | Yanıt |
|---|---|
| `GET /api/health` | `{"status":"ok","aoi":"<id>","data_version":"<tarih>"}` |
| `GET /api/aoi` | `{"id","name","bbox":[w,s,e,n],"stats":{"line_km","segment_count","tier_counts":{"kritik","yuksek","orta","dusuk"},"workorder_count"}}` |
| `GET /api/segments?tier=kritik,yuksek&bbox=w,s,e,n` | GeoJSON FeatureCollection. Özellikler: `segment_id, line_id, voltage_class, risk, tier, p_ignition, consequence, top_factors:[{key,label_tr,label_en,contribution}]` |
| `GET /api/segments/{segment_id}` | Yukarıdakiler + `raw:{faktör: ham değer}` + `contrib:{faktör: katkı}` + `chm_year` |
| `GET /api/workorders?limit=50&format=json\|geojson` | Açıklık listesi (risk-model-spec §4 alanları) |
| `GET /api/workorders/export?format=csv\|geojson\|gpkg` | Dosya indirme (CSV UTF-8 BOM) |
| `GET /api/scenario/dates` | `[{"date","max_gust_kmh"}]` |
| `GET /api/scenario?date=YYYY-MM-DD&gust_kmh=50&min_tier=yuksek` | `{"date","inputs","district_wide":{"line_km","buildings"},"targeted":{"line_km","buildings","line_ids":[],"risk_covered_ratio"},"segments":FeatureCollection,"note_tr","note_en"}` |
| `GET /api/backtest` | `{"as_of","season","n_events","top10":{"share","expected","lift","ci95":[lo,hi]},"top20":{...},"baselines":{...},"limitations_tr":[],"limitations_en":[]}` |
| `GET /api/backtest/events` | GeoJSON (olay kümeleri) |
| `GET /api/meta/sources` | `[{"name","license","attribution","url"}]` |
| `GET /` | web/index.html (statik) |

## Arayüz düzeni
- **Sol panel (sekmeler):** İş listesi · Senaryo · Doğrulama · Hakkında/Kaynaklar.
- **Orta:** harita.
- **Sağ:** detay çekmecesi.
- **Üst bant:** API'den gelen 3 sayaç.
- **Alt bilgi:** atıflar.
- **Dil:** TR/EN düğmesi.

## Çevrimdışı mod (F5)
- MapLibre JS ve CSS dosyaları web/vendor/ altında yerel kopya olarak durur.
- Altlık:
  - Çevrimiçi: ücretsiz ve anahtarsız bir stil (frontend-dev lisansı doğrular).
  - Çevrimdışı yedek: AOI için önceden hazırlanmış basit vektör katmanlar (ilçe sınırı, ana yollar, yerleşim) veya yerel PMTiles.
- Sunucu çalışırken ağ çağrısı yapmaz. Tüm veriler önceden hesaplanmıştır.

## Performans bütçesi
- **Pipeline:** Pilot ilçe önbellekten en fazla 30 dakikada çalışır; işlem başına bellek en fazla 4 GB.
- **API:** Yanıtlar 500 ms'nin altındadır; tek GeoJSON yanıtı en fazla 5 MB'tır (gerekirse sadeleştirme).
- **Arayüz:** İlk açılış 3 saniyenin altındadır.

## Platform
- Hedef: Windows ve macOS (Claude Code masaüstü); Python 3.12 ve uv.
- Kabuk betiği yerine Python betiği kullanılır; yollar pathlib ile.
- Node.js yalnızca Playwright MCP (test) için gerekir; uygulama Node gerektirmez.
