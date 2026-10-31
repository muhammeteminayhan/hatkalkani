# QA F4-3: Tam test turu ve 90 sn demo akışı

Tarih: 2026-10-31. Ortam: Windows 11, Python 3.12 (uv), tarayıcı Playwright 1920×1080 (sonradan 1044×750'ye düştü, bkz. D3).
Model: claude-haiku-5-5. Sunucu: `scripts/serve.py --port 8013` (kapatıldı).

## 1. Lint ve testler

| Adım | Komut | Sonuç |
|---|---|---|
| Lint | `uv run ruff check . > data/interim/logs/ruff.log` | GEÇTİ, exit 0, "All checks passed!" |
| Testler | `uv run pytest -o addopts="" -m "not network" -rs` | GEÇTİ: **215 passed, 0 failed, 0 skipped**, 2 deselected (network) |
| Ağ testleri | `uv run pytest -o addopts="" -m network --co -q` | 2 test toplandı (çalıştırılmadı) |

Not: `pyproject.toml` `addopts` içinde `-q` var; komuta `-q` eklenince özet satırı bastırılıyor (`pytest.log` yalnızca noktaları içeriyor). Sayı için `-o addopts=""` kullanıldı. Log: `data/interim/logs/pytest_summary.log`.

## 2. İdempotentlik

- Çalıştırma öncesi ve sonrası sha256: `data/interim/logs/sha_before.txt`, `sha_after.txt`. **9/9 dosya birebir aynı** (backtest.json, features_*.meta.json, risk_*.meta.json, risk_*.parquet, scenario_2025-06-29.json, scenario_dates.json).
- Komut: `uv run python scripts/run_pipeline.py --aoi izmir_menderes --stage all` → **exit 0, 140,1 sn** (önbellekten). Dosyaların mtime'ları yenilendi; içerik değişmedi, yani çıktılar deterministik.
- Dikkat: süre ilk çalıştırma değildir. chm_dates 51,4 sn, features 35,4 sn baskın aşamalar.
- MANIFEST: "MANIFEST validation OK" satırı çıktıda var.

## 3. Disk (README için)

| Yol | Boyut |
|---|---|
| `data/` | 394 MB |
| `data/raw` | 116 MB |
| `data/interim` | 275 MB |
| `data/processed` | 3,2 MB |
| `.venv` | 653 MB |

## 4. API (ARCHITECTURE v0.2, ms = curl time_total)

| Uç nokta | HTTP | Bayt | ms |
|---|---|---|---|
| /api/health | 200 | 103 | 4 |
| /api/aoi | 200 | 295 | 3 |
| /api/aoi?as_of=2025-05-31 | 200 | 295 | 4 |
| /api/aoi/boundary | 200 | 48183 | 5 |
| /api/segments?tier=kritik,yuksek&bbox=... | 200 | 121423 | 16 |
| /api/segments?tier=...(4 kademe) | 200 | 578411 | 34 |
| /api/segments?tier=kritik,yuksek&as_of=2025-05-31 | 200 | 121602 | 6 |
| /api/segments/155462929_0001 | 200 | 5341 | 3 |
| /api/workorders?limit=50&format=json | 200 | 40140 | 4 |
| /api/workorders?format=geojson | 200 | 50013 | 4 |
| /api/workorders/export?format=csv | 200 | 33525 | 5 |
| /api/workorders/export?format=geojson | 200 | 73587 | 4 |
| /api/workorders/export?format=gpkg | 200 | 147456 | 5 |
| /api/scenario/dates | 200 | 747 | 4 |
| /api/scenario?date=2025-06-29&gust_kmh=50&min_tier=yuksek | 200 | 553127 | 14 |
| /api/backtest | 200 | 14604 | 4 |
| /api/backtest/events | 200 | 4466 | 4 |
| /api/meta/sources | 200 | 1951 | 3 |
| /api/meta/factors | 200 | 686 | 3 |
| / | 200 | 5663 | 6 |

Tüm uç noktalar 200. En yavaş yanıt 34 ms (500 ms bütçesinin altında). CSV UTF-8 BOM (`efbbbf`) doğrulandı. Log: `data/interim/logs/api_timing.tsv`.

## 5. Demo akışı (90 sn)

| Adım | Sonuç | Ekran görüntüsü |
|---|---|---|
| Açılış: 3 sayaç (92,4 km / 46 kritik / 76 açıklık), harita, kademe renkleri | GEÇTİ | docs/screens/demo-01.png |
| İş listesi, #1 tıklama → yakınlaşma, detay (skor 77,6, Kritik, 3 neden Türkçe, ham değerler, koordinat, "Haritada aç") | GEÇTİ | docs/screens/demo-02.png |
| İndirme: CSV, GeoJSON, GPKG iner | GEÇTİ (aşağıda) | — |
| Senaryo: tarih, rüzgâr kaydırıcısı, kademe, karşılaştırma kartı, "Vekil ölçüm" notu | GEÇTİ | docs/screens/demo-03-senaryo.png, demo-04.png |
| Doğrulama: harita 2025-05-31'e geçiyor (etiket + `as_of=2025-05-31` isteği) | GEÇTİ | docs/screens/demo-05-dogrulama.png |
| Doğrulama: yangın noktaları haritada | KISMEN (bkz. O1) | demo-05b-dogrulama-olaylar.png, demo-05c-dogrulama-olay-genis.png |
| Sekmeden çıkınca güncele dönüş | KISMEN (bkz. D5) | — |

**Ölçümler:**
- İlk açılış: sayfa yükleme 243 ms, harita canvas 367 ms, `window.__hk.ready` 526 ms. Kabul kriteri (3 sn) **GEÇTİ**.
- Konsol (ilk açılış, çevrimiçi): 0 hata.
- Dil: varsayılan TR; "English" tıklamasında başlık, sekmeler ("Work list", "Scenario", "Validation", "About"), KPI etiketleri ve buton İngilizceye geçti. **GEÇTİ**.
- İndirmeler: CSV `hatkalkani_isemri_2026-10-30.csv` 33525 bayt, BOM var, 76 satır. GeoJSON 76 öznitelik. GPKG SQLite başlıklı, katman `workorders`. **Üçü GEÇTİ.** Dosyalar: `data/interim/logs/dl/`.
- Senaryo kaydırıcısı (2025-06-29, Yüksek): 50 km/h → hedefli 83,4 km, 3.032 bina, %92; 80 km/h → 3,4 km, 17 bina, %4. **Değiştiriyor, GEÇTİ.**
- Kademe seçimi: 50 km/h'de Yüksek → Kritik: 83,4 km → 82,0 km (3.032 → 3.024 bina). 80 km/h'de sonuç değişmiyor (bkz. O4). **Kısmen GEÇTİ.**
- Doğrulama alt metinleri: üst %10 ve %20, taban çizgileri, duyarlılık (1000/2000 m), vaka incelemesi, sınırlılıklar hepsi görünür.

## 6. Çevrimdışı

- Yöntem: `page.route` ile `tiles.openfreemap.org` ve diğer harici istekler iptal edildi, sayfa yeniden yüklendi.
- Sonuç: **GEÇTİ.** Engellenen yalnızca 1 istek (`styles/positron`). Sayaçlar (92,4 / 46 / 76), liste (54 öğe) ve alt bilgi yüklendi. Alt bilgi "Altlık çevrimdışı: yalnızca ilçe sınırı ve hatlar gösteriliyor" yazıyor. Konsoldaki tek hata engellenen isteğe ait `ERR_FAILED`.
- Ekran görüntüsü: docs/screens/demo-offline.png (1044×750, bkz. D3).

## 7. Bulgular

Kritik: yok.

**Yüksek**
- **Y1 (demo anlatımı):** Doğrulama sonucu zayıf. Hat yakınında yalnızca 2 olay var (n=2), lift 0,0×, yakalanan olay payı %0 (0/2), "n=2: yorumlanamaz" etiketi var. Arayüz bunu dürüstçe işaretliyor, ama "yakaladığı olay payı beklenen pay" anlatımı jüriye %0 olarak gider. Yazılım hatası değil; sunum riski.
  - Yeniden üretme: `curl http://127.0.0.1:8013/api/backtest`, sekme Doğrulama.

**Orta**
- **O1:** Varsayılan Doğrulama kadrajında mor yangın noktaları görünmüyor. Yalnızca iki kademe uzaklaştırınca görünüyor (demo-05c). Demo adımı "2025 yangın noktaları haritada" için kadrajın ayarlanması gerekiyor.
  - Yeniden üretme: Doğrulama sekmesine geç, varsayılan zoom'da bak; sonra Zoom out ×2.
- **O2:** "Hedefli" kesinti neredeyse ilçe geneli kadar. Varsayılan 50 km/h, Yüksek: 83,4 / 92,4 km (%90). Hat birimi kesintisi nedeniyle hedefli kart zayıf bir karşılaştırma veriyor (bina 3.032 vs 3.469).
  - Yeniden üretme: `curl "http://127.0.0.1:8013/api/scenario?date=2025-06-29&gust_kmh=50&min_tier=yuksek"`.

**Düşük**
- **O4:** 80 km/h'de tüm kademeler aynı sonucu veriyor (3,4 km). Rüzgâr eşiği baskın; kademe seçimi bu eşikte etkisiz. Bilgi amaçlı.
- **O5:** 2025-06-28, 06-29, 06-30 için 50 km/h'de hedefli sonuç birebir aynı (83,371 km). Rüzgâr serisi tarihe göre farklı (71,3 / 83,5 / 62,3 km/h) ama eşiğin üstünde kalan hatlar aynı. Hata değil; açıklama gerekebilir.
- **O6:** Tarih listesinde 4 gün var, `data/processed/izmir_menderes/` içinde yalnızca `scenario_2025-06-29.json` var. Diğer günler istekte hesaplanıyor (200 OK, 06-27 için 3,4 km). "Önceden hesaplanmış" ifadesiyle dosya durumu tutarsız.
- **D1:** Zoom out sırasında konsolda 3 uyarı: "Expected value to be of type number, but found null" (MapLibre, blob). Hata değil ama konsol temiz olmalı kabul kriterine aykırı.
  - Yeniden üretme: Doğrulama sekmesinde Zoom out ×2, `browser_console_messages level=warning`.
- **D2:** `pyproject.toml` `addopts` içindeki `-q` nedeniyle pytest özeti bastırılıyor. Tek satır düzeltme önerisi (yalnız rapor, kod değiştirilmedi).
- **D3:** TR/EN ve çevrimdışı çalıştırmalardan sonra tarayıcı görünüm alanı 1044×750'ye düştü. Bu ekran görüntüleri 1920×1080 değil. Yeniden üretmek için `browser_resize 1920×1080` çağrısı, sonra tekrar.
- **D4:** pytest uyarıları: shapely `transform()` kullanımdan kalktı (`src/hatkalkani/ingest/chm.py:425`), httpx/starlette test istemcisi uyarısı.
- **D5:** Doğrulama → İş listesi dönüşünde "2025-05-31" etiketi kayboldu (GEÇTİ). Ancak `/api/segments` (as_of'suz) isteği yakalanamadı; güncel veri yeniden yükleniyor mu tam doğrulanmadı.

## 8. README için ölçülen değerler

- Disk: `data/` 394 MB, `.venv` 653 MB (README'deki [DOĞRULANACAK] alanı).
- Pipeline (önbellekten, tüm aşamalar): 140,1 sn. İlk çalıştırma (FIRMS indirmesi dahil) bu turda ölçülmedi.
