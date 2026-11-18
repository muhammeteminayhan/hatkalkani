# QA-POR: yayın öncesi son kontrol

Tarih: 2026-11-18. Ana klasör: `C:/Users/merto/Desktop/hatkalkani`. Kod değiştirilmedi. Port 8000 kullanılmadı. `.env` okunmadı.

| Adım | Sonuç | Kanıt / not |
|---|---|---|
| 1a. `uv run ruff check src tests scripts` | KALDI | 5 × E501 (satır > 100), hepsi `scripts/make_static_scenarios.py` (izlenmeyen dosya): satır 40, 47, 48, 54, 58. `src/` ve `tests/` temiz. Log: `data/interim/logs/ruff-por.log` |
| 1b. `uv run pytest` | GEÇTİ | 233 passed, 2 deselected, 2 uyarı (shapely `transform` deprecation). Exit 0. Log: `data/interim/logs/pytest-por.log` |
| 2a. Canlı sunucu `--port 8017`, health | GEÇTİ | `/api/health` 200, 1 sn içinde. |
| 2b. API uç noktaları (ARCHITECTURE.md) | GEÇTİ | 15/15 HTTP 200. Boyutlar `data/interim/logs/api-por.log` içinde (örn. segments 121 KB, scenario 553 KB, workorders export csv 33 KB, gpkg 147 KB). |
| 2c. Canlı TR/EN 4 sekme, 1920×1080, konsol | GEÇTİ | 4 sekme TR (İş listesi, Senaryo, Doğrulama, Hakkında) ve EN (Work list, Scenario, Validation, About) açılıyor. Konsol: 0 hata, 0 uyarı. Ekran: `docs/screens/live-tr-*.png` |
| 2d. Sayfa kaydırma çubuğu yok | GEÇTİ | `html`/`body` overflow hidden; doküman yüksekliği 1080 = görünüm 1080. |
| 2e. Sol liste kendi içinde kayıyor | GEÇTİ | `SECTION.pane` scrollHeight 7431 / clientHeight 746 (İş listesi); aynı yapı diğer sekmelerde de var. |
| 2f. #1 iş paketi detayı, 3 neden | GEÇTİ | Detayda "neden" bölümü: Hatta yakın yüksek ağaç (+7,5), Hatta devrilebilecek ağaç (+5,3), Kuru bitki örtüsü (+4,1). Ham değerler ve "Haritada aç" görünür. |
| 2g. Senaryo kaydırıcısı tabloyu değiştiriyor | KALDI | UI'da kaydırıcı 50 → 17 km/sa yapıldığında tablo sayıları değişmedi (hedefli 83,4 km, 3.032 bina, %92; yalnız eşik etiketi değişti). API: `date=2025-06-29`, 17 km/sa → hedefli 83,37 km; 80 km/sa → 3,37 km (değişiyor). Yani duyarlılık yalnız yüksek eşiklerde görünüyor; 17 ve 50 aynı sonuç veriyor. Neden: doygunluk (tier filtresi) mi, eşik kalibrasyonu mu, bilinmiyor. Tekrar: `curl "http://127.0.0.1:8017/api/scenario?date=2025-06-29&gust_kmh=50&min_tier=yuksek"` ve `gust_kmh=17` karşılaştır. |
| 2h. Statik bant canlı modda görünmüyor | GEÇTİ | "Statik" metni içeren görünür öğe yok. |
| 2i. `docs/screens/live-check.png` kaydı | GEÇTİ | `docs/screens/live-check.png` (#1 detayı açık, TR). |
| 2j. Sunucu durduruldu | GEÇTİ | PID 6480 kapatıldı; `/api/health` artık yanıt vermiyor. |
| 3a. Statik kopya `scratchpad/hatkalkani/`, `http.server` 8018 | GEÇTİ | Kopya 200; index ve mock dosyaları 200. |
| 3b. 4 sekme açılıyor | GEÇTİ | TR 4 sekme; her biri içerik gösteriyor. Yükleme 161 ms. |
| 3c. Statik bant görünüyor | GEÇTİ | "Statik anlık görüntü" ve "Statik demo — 31 Ekim 2026 çıktılarının anlık görüntüsü…" görünür. |
| 3d. Konsol temiz | GEÇTİ | Sayfa yeniden yüklendiğinde 0 hata, 0 uyarı. İlk turda 1 × 404 görüldü; kaynağı test betiğimin sayfa içinde `api/workorders/export` yolunu elle çağırması (statikte yok). Uygulamanın kendisi bu yolu çağırmıyor (`web/app.js` `mock/` yollarına eşliyor). |
| 3e. CSV indirme | GEÇTİ | `hatkalkani_isemri_2026-10-30.csv` indi, 33.525 bayt, UTF-8 BOM, 77 satır. |
| 3f. Dış altlık (tiles.openfreemap.org) | NOT | Bu ortamda dış karo istekleri başarısız (`requestfailed`). Konsol hatası olarak sayılmadı; yerel yedek altlık bu turda ayrıca doğrulanmadı. |
| 4. README.md ve README.en.md göreli bağlantıları | GEÇTİ | Her iki dosyada 32 göreli bağlantı var ve hepsi mevcut (`.claude/agents/`, `CLAUDE.md`, `LICENSE`, `docs/*`, `docs/reports/*`, `docs/screens/*`, `pyproject.toml`, `tests/features/test_leakage.py`, `tests/model/test_score_leakage.py`). Ek not: README'de backtick içinde `data/manual/edas/` geçiyor ve yok; bağlantı değil, EDAŞ veri klasörü yer tutucusu olabilir. Doğrulanması gerekiyor. |

## Ekran görüntüleri
- `docs/screens/live-check.png`
- `docs/screens/live-tr-İş-listesi.png`, `live-tr-Senaryo.png`, `live-tr-Doğrulama.png`, `live-tr-Hakkında.png`, `live-tr-senaryo-kaydirici.png`
- `docs/screens/qa-por-static-acilis.png`, `docs/screens/qa-por-static-detay.png`

## Özet
- Yayın engeli: ruff (5 E501, izlenmemiş `scripts/make_static_scenarios.py`) ve senaryo kaydırıcısının tabloyu değiştirmemesi (17–50 km/sa aralığında).
- Düzeltme yapılmadı; bu rapor yalnızca bulguları kaydeder.
