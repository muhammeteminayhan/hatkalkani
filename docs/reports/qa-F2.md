# QA-F2 — Faz 2 kapanış doğrulaması

Model: claude-haiku-5-5 (Haiku 5.5)
Tarih: 2026-10-31
Ortam: Windows 11, Git Bash, uv (`$HOME/.local/bin`)

## Özet

| Adım | Komut | Sonuç |
|---|---|---|
| 1. Lint | `uv run ruff check .` | GEÇTİ — "All checks passed!", çıkış 0 |
| 2. Testler | `uv run pytest -q` | GEÇTİ — çıkış 0; verbose koşuda **48 passed, 2 deselected** (ağ testleri `-m 'not network'` ile atlandı) |
| 3. Önce sha256 | sha256sum (5 dosya) | Alındı (aşağıda) |
| 4. Pipeline ingest | `uv run python scripts/run_pipeline.py --aoi izmir_menderes --stage ingest` | GEÇTİ — çıkış 0; "MANIFEST validation OK"; modül toplamı 28.5 sn |
| 5. Sonra sha256 | sha256sum (5 dosya) | GEÇTİ — 5/5 aynı (idempotent) |

Kabul kriterleri: ruff temiz ✔ · pytest geçer ✔ · pipeline önbellekten < 5 dk ve çıkış 0 ✔ · sha256 önce/sonra aynı ✔

## Ayrıntılar

### Adım 1 — ruff
- Komut: `uv run ruff check .`
- Sonuç: `All checks passed!`, çıkış 0.

### Adım 2 — pytest
- Komut: `uv run pytest -q` → çıkış 0, 48 test geçti. Log: `data/interim/logs/pytest-F2.log`.
- `-q` modu özet satırını yazmadı (aşağıdaki Risk 1'e bak). Geçen/atlanan sayıları ayrı bir koşuyla aldım: `uv run pytest -v -rs -p no:warnings` → `48 passed, 2 deselected in 3.37s`. Log: `data/interim/logs/pytest-F2-verbose.log`.
- Ağ testleri (`network` işaretli) varsayılan olarak atlandı; onaylanmış davranış.
- Uyarı (hata değil): `tests/ingest/test_chm.py` içinde `shapely.ops.transform` DeprecationWarning (`src/hatkalkani/ingest/chm.py:423`).

### Adım 3 ve 5 — sha256 karşılaştırması

| Dosya | Önce (sha256) | Sonra (sha256) | Durum |
|---|---|---|---|
| data/processed/izmir_menderes/segments.parquet | 8a3155ed17f7149b8a68f4f35ea64744e8c3373839a04b279b41d2e85d0ea604 | aynı | AYNI |
| data/interim/izmir_menderes/chm_segment_stats.parquet | 2660c1f1f499566c7c218f617bcb57246a31d3f0a8be7491d4fe905ffcd11adc | aynı | AYNI |
| data/interim/izmir_menderes/firms.parquet | e534cd09f98c2259f5a1ed7193693d62c91981d32b983e277909334f84dcb2c9 | aynı | AYNI |
| data/interim/izmir_menderes/buildings.parquet | 9f2a28b1f8a2818a0ae9df19cfc4a85fe2f09b30cb695ba8e1eb027d35fe8bd3 | aynı | AYNI |
| data/interim/izmir_menderes/s2_ndvi_backtest.tif | 6d0bff75bbb862412a497493a822b3b782980cae21ad03ac380381a3ac9ddc3a | aynı | AYNI |

Not: `segments.parquet`, `firms.parquet` ve `buildings.parquet` dosyalarının değişiklik zamanı çalıştırmayla güncellendi (02:27), içerik hash'i değişmedi. `chm_segment_stats.parquet` ve `s2_ndvi_backtest.tif` bu koşuda yeniden yazılmadı (zaman damgası eski).

### Adım 4 — pipeline ingest
- Komut: `uv run python scripts/run_pipeline.py --aoi izmir_menderes --stage ingest` (`timeout 600` ile sarıldı).
- Çıkış kodu: 0.
- Satır 46: `MANIFEST validation OK`.
- Modül süreleri (sn): boundary 2.4, lines 2.3, segments 2.5, sentinel2 2.8, dem 2.8, worldcover 2.8, chm 2.9, buildings 5.0, firms 2.3, weather 2.6; **toplam 28.5**.
- Duvar saati ölçülmedi (Git Bash'te `bc` yok); modül toplamı ve 600 sn zaman aşımının dolmaması, önbellekten 5 dakika kriterinin karşılandığını gösteriyor.
- Ağdan büyük indirme başlamadı; koşu önbellekten tamamlandı.
- Log: `data/interim/logs/pipeline-F2.log`.

## Riskler / Bulgular

1. **Pytest özet satırı yok (düşük).** `pyproject.toml` satır 52: `addopts = "-q -m 'not network'"` ve komut satırındaki `-q` birleşince pytest `-qq` davranışına geçiyor; özet satırı (`N passed, M skipped`) basılmıyor. Çıkış kodu doğru, ama CI logundan geçen/atlanan sayısı okunamıyor. Öneri: `addopts` içindeki `-q` kaldırılsın (ör. `addopts = "-m 'not network'"`). Bu rapor kod değiştirmedi.
2. **DeprecationWarning (düşük).** `src/hatkalkani/ingest/chm.py:423` — `shapely.ops.transform` yerine `shapely.transform` kullanılmalı.
3. **Wall-clock süresi ölçülmedi.** Modül toplamı 28.5 sn; kesin duvar saati için `time` ile yeniden koşu önerilir.

## Üretilen log dosyaları
- data/interim/logs/pytest-F2.log
- data/interim/logs/pytest-F2-verbose.log
- data/interim/logs/pipeline-F2.log
