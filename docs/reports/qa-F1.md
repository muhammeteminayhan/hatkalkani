Model: Haiku 5.5 (claude-haiku-5-5)

# QA-F1 — Faz 1 kapanış kontrolü

Tarih: 2026-10-30
Ortam: Windows 11, Git Bash, `uv` (`export PATH="$HOME/.local/bin:$PATH"`)
Kapsam: duman testi, ruff, önbellekten keşif betiği yeniden üretimi. Kod değiştirilmedi.

## Sonuç özeti

| Adım | Durum | Sonuç |
|---|---|---|
| 1. `uv run pytest -q tests/test_smoke.py` | GEÇTİ | Çıkış kodu 0, `.` ile 1 test geçti. Özet satırı `-q` nedeniyle yazılmadı; toplanan test sayısı 1 (`--collect-only`). |
| 2. `uv run ruff check notebooks/f1_candidate_stats.py` | GEÇTİ | "All checks passed!", çıkış kodu 0 |
| 3a. CSV sha256 (çalıştırma öncesi) | GEÇTİ | Alınan değerler aşağıda |
| 3b. `uv run python notebooks/f1_candidate_stats.py --districts Menderes Çeşme Ödemiş Seferihisar Torbalı` | GEÇTİ | Çıkış kodu 0, süre 7 sn (hedef 2 dk altı). Ağdan indirme görülmedi. |
| 3c. CSV sha256 (çalıştırma sonrası) | GEÇTİ | İki hash da önceki değerle aynı; `diff` farksız. |

## Hash değerleri

- `data/interim/f1_candidates/izmir_landcover.csv`
  `4dbf4c74b451925f47eada18652c98b402c89015d02de0f57cf71132a5189206`
- `data/interim/f1_candidates/candidate_corridors.csv`
  `c7dcd650007907d65f8dfeaf5ab0a716aaf51115e910725fcc9717aa7854475d`

## Betik çıktısındaki gözlemler (hata değil, not)

- Konsolda Türkçe ilçe adları bozuk görünüyor (`�e�me`, `Torbal�`). CSV'lerin kendisi UTF-8 ve `Çeşme`, `Ödemiş` doğru yazılmış. Sorun betiğin stdout kodlamasında; Windows konsolu UTF-8 değil. Yalnızca ekran çıktısını etkiliyor.
- Betik `skip metadata ... (budget)` satırları yazdı (49 MB, 63 MB, 55 MB). Bunlar bütçe nedeniyle atlanan dosyalar; indirme değil.
- `districts: 30` ve `izmir_landcover.csv: 30 rows` satırları, verilen 5 ilçeye göre ilk satırlarla tutarlı görünmüyor. Ayrıca `candidate_corridors.csv: 5 rows`. Satır sayılarının neyi saydığı betikte doğrulanmalı; bu QA'da yalnızca kaydedildi.

## Açık noktalar

- Pytest çıktısında özet satırı yok (`-q` ile birlikte `addopts` içinde `-q` olabilir). Geçiş yine de çıkış kodu 0 ile doğrulandı.
- Ekran çıktısındaki bozuk karakterler düzeltilmedi (kod değiştirme yetkim yok).

## Tekrarlama komutları

```
export PATH="$HOME/.local/bin:$PATH"
cd /c/Users/merto/Desktop/hatkalkani
uv run pytest -q tests/test_smoke.py
uv run ruff check notebooks/f1_candidate_stats.py
sha256sum data/interim/f1_candidates/izmir_landcover.csv data/interim/f1_candidates/candidate_corridors.csv
uv run python notebooks/f1_candidate_stats.py --districts Menderes Çeşme Ödemiş Seferihisar Torbalı
```

Ham betik günlüğü: `C:\Users\merto\AppData\Local\Temp\claude\C--Users-merto-Desktop-hatkalkani\3746d98c-ff76-4e70-852c-dfffdae65026\scratchpad\f1_run.log`
