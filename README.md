# HatKalkanı

Elektrik dağıtım hatlarından kaynaklanan orman yangını riskini 100 m'lik hat parçası düzeyinde puanlayan karar destek aracı. COP31 İklim Teknolojileri Creathonu için geliştiriliyor.

- **Koridor risk haritası:** 0–100 skor ve skoru yükselten 3 neden
- **Budama/drone iş emri listesi:** CSV, GeoJSON ve GeoPackage
- **Önleyici kesinti senaryosu:** rüzgârlı günde ilçenin tamamı yerine yalnızca riskli hatlar
- **Geriye dönük test:** 2025 yangın sezonu

## Claude Code ile çalışma
Bu depo, Claude Code masaüstünde çok ajanlı çalışmak üzere hazırlanmıştır.

1. Önce `MANUAL_TASKS.md` dosyasındaki "Başlamadan önce" adımlarını tamamlayın.
2. `KICKOFF_PROMPT.md` dosyasındaki ilk mesajı ana oturuma yapıştırın.
3. Sonraki oturumlarda aynı dosyadaki kısa devam mesajını kullanın.

| Dosya | İçerik |
|---|---|
| `CLAUDE.md` | Ana oturumun (orkestratör) protokolü ve model yönlendirme tablosu |
| `.claude/agents/` | 10 alt ajan; her birinin modeli ve effort'u burada |
| `.claude/skills/` | Ajanlara önceden yüklenen bilgi paketleri ve `/durum` komutu |
| `docs/PLAN.md` | Fazlar, görevler, kabul kriterleri, kontrol noktaları |
| `docs/STATUS.md` | Canlı durum panosu |

## Çalıştırma
F2–F4 tamamlanınca doc-writer bu bölümü doldurur. Hedef komutlar:

```
uv sync
uv run python scripts/run_pipeline.py --aoi <id> --stage all
uv run python scripts/serve.py     # http://127.0.0.1:8000
uv run pytest
```

## Kaynaklar
Veri, yazılım ve görsel kaynakları: `docs/ATTRIBUTIONS.md`
