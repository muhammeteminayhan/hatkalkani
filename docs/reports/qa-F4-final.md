# QA-CLONE: Commit 1ff143c temiz klon testi (F4 final)

Tarih: 2026-10-31. Klon: `git clone C:/Users/merto/Desktop/hatkalkani <scratch>/clean-clone` (HEAD 1ff143c). Klon yerinde bırakıldı, silinmedi.
Veri: `data/raw`, `data/interim`, `data/processed` ana klasörden kopyalandı (raw 165, interim 228, processed 24 dosya). `.env` okunmadı, kopyalanmadı. Ingest çalıştırılmadı.

## Adımlar

| adım | komut | sonuç | süre |
|---|---|---|---|
| 1. Klon + bağımlılık | `git clone ...` ; `uv sync` | GEÇTİ (exit 0) | sync 6 sn |
| 2. Veri kopyası | kopyalama (raw, interim, processed) | GEÇTİ | ölçülmedi |
| 3a. Lint | `uv run ruff check src tests` | GEÇTİ ("All checks passed!") | 1 sn |
| 3b. Test | `uv run pytest` | GEÇTİ: 233 passed, 2 deselected, 2 warnings | 39 sn |
| 4a. features | `run_pipeline.py --aoi izmir_menderes --stage features` | GEÇTİ (rc=0) | 16 sn |
| 4b. score | `... --stage score` | GEÇTİ (rc=0) | 4 sn |
| 4c. scenario | `... --stage scenario` | GEÇTİ (rc=0) | 4 sn |
| 4d. backtest | `... --stage backtest` | GEÇTİ (rc=0) | 5 sn |
| 4e. sha256 | sha256sum ana klasör ve klon | backtest.json ve scenario_2025-06-29.json: EŞLEŞTİ. risk_2026-10-30.parquet ve risk_2025-05-31.parquet: bayt farklı, İÇERİK EŞİT (pyarrow ile 925x48, şema ve değerler aynı; fark dosya metadatası) | - |
| 5a. Sunucu | `serve.py --port 8015` (arka plan) | GEÇTİ; health 200, log'da hata yok | - |
| 5b. API | 15 istek (aşağıda) | GEÇTİ: hepsi 200 | - |
| 5c. Tarayıcı, 1920x1080 | Playwright: 4 sekme TR + EN | GEÇTİ; konsol error/warning yok | ilk yükleme 159 ms |
| 5d. Senaryo kaydırıcısı | değer 0 -> 87 (EN) | GEÇTİ: tablo metni değişti (1535 -> 1529 karakter) | - |
| 5e. "Bilgi vermiyor" | Doğrulama sekmesi (TR) | GEÇTİ: metin var | - |
| 6. Kapanış | sunucu süreci durduruldu | GEÇTİ: 8015 kapandı | - |

API yanıtları (HTTP kodu, boyut): /api/health 200 103 B; /api/aoi 200 295 B; /api/aoi/boundary 200 48 KB; /api/segments?tier=kritik,yuksek 200 121 KB; /api/workorders?format=json 200 40 KB; /api/workorders?format=geojson 200 50 KB; /api/workorders/export csv 200 34 KB; export geojson 200 74 KB; export gpkg 200 147 KB; /api/scenario/dates 200 747 B; /api/scenario?date=2025-06-29&gust_kmh=50&min_tier=yuksek 200 553 KB; /api/backtest 200 21 KB; /api/backtest/events 200 4 KB; /api/meta/sources 200 2 KB; /api/segments/{id} 200 5 KB.

Playwright ekran görüntüleri (ana klasöre yazılmadı): `<scratch>/qa-01-acilis-tr.png`, `qa-02-tr-sekme1..4.png`, `qa-03-senaryo-kaydirici.png`, `qa-04-en-sekme1..4.png`, `qa-05-en-senaryo-kaydirici.png`.
Sekme adları: TR: İş listesi, Senaryo, Doğrulama, Hakkında. EN: Work list, Scenario, Validation, About.

## Bulgular

1. **Kırmızı adım yok.** Lint, testler, pipeline, API, arayüz ve sunucu kapanışı geçti.
2. **Parquet dosyaları bayt olarak farklı** (risk_2026-10-30, risk_2025-05-31). İçerik eşit. Bayt düzeyinde sha256 eşleşmesi beklenmemeli.
3. **Harita karoları çevrimiçi:** Tarayıcıda `tiles.openfreemap.org` karo istekleri `net::ERR_ABORTED` ile iptal edildi (konsol error/warning değil, requestfailed). Çevrimdışı akış için yerel altlık gerekir. Bu koşuda ağ açıktı, çevrimdışı test edilmedi.
4. **Testlerde 2 deselected** ve 2 deprecation uyarısı var (shapely.ops.transform, starlette httpx). Zararsız, sunum öncesi temizlenebilir. Deselected'ın nedeni incelenmedi.
5. Klon dizinini silmeye yönelik ilk bash komutu bir güvenlik kancası tarafından engellendi; silme yapılmadı, komut silme içermeden yeniden çalıştırıldı. Klon silinmedi.
6. Arka plan sunucu görevi "exit 127" ile bildirildi; bu, sunucuyu bizim durdurmamızdan kaynaklanıyor. Sunucu logunda hata yok.

## Dosya değişiklikleri
Ana klasörde yalnız bu rapor yazıldı. src/, web/, tests/, config/, data/ değiştirilmedi.
