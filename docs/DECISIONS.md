# Karar kayıtları (ADR)

Her önemli kararı aşağıdaki kalıpla ekle; eski kararları silme, geçersizse "yerini aldı: ADR-0xx" yaz.

```
## ADR-0xx — <başlık>  (tarih, karar veren)
Bağlam: …
Karar: …
Sonuçlar / ödünleşimler: …
```

## ADR-001 — Orkestrasyon: alt ajanlar  (2026-10-30, kurulum)
- **Bağlam:** Ana oturumun bağlamı temiz kalmalı ve maliyet kontrol edilmeli. Claude Code'un "agent teams" özelliği deneysel; belgelerine göre tek oturumdan çok daha fazla token harcıyor.
- **Karar:** Tek ana oturum orkestratör olur. İşleri `.claude/agents` altındaki odaklı alt ajanlar yapar ve kısa rapor döner.
- **Ayarlar:**
  - Fork modu kapalı.
  - Alt ajanlar başka alt ajan başlatamaz (derinlik 1).
  - Aynı anda en fazla 5 alt ajan çalışır; bunlardan en fazla 1'i Opus ajanıdır.

## ADR-002 — Teknoloji yığını  (2026-10-30, kurulum)
- **Karar:** Python 3.12 + uv, geopandas/rasterio, FastAPI; arayüz derleme adımı olmayan tek sayfa MapLibre.
- **Gerekçe:** 4 kişilik ekip ve 24 saatlik finalde hızlı değişiklik. Node derleme zinciri yok. Çevrimdışı demo kolay.

## ADR-003 — Kural tabanlı ilk model  (2026-10-30, kurulum)
- **Bağlam:** Hat kaynaklı tutuşma konumları kamuya açık değil; etiketli veri yok.
- **Karar:** v0.1 yapılandırılabilir ve açıklanabilir bir kural tabanlı skordur. ML, pilot şirket verisiyle sonraki aşamada gelir.
- **Değerlendirme:** FIRMS ile dürüst bir geriye dönük test yapılır.

## ADR-004 — Pilot il: İzmir  (2026-10-30, kurulum)
- **Gerekçe:**
  - 2025'te elektrik kaynaklı olduğu bildirilen yangınlar oldu.
  - GDZ kuvvetli rüzgârda önleyici kesinti yaptı.
- **Seçim:** İlçe F1 sonunda (K1) seçilir.

## ADR-005 — Model yönlendirme  (2026-10-30, kurulum)
| Model | Kullanım |
|---|---|
| Opus 5.5 | Orkestratör (oturumda `/effort max`), risk-modeler ve code-reviewer (max) |
| Sonnet 5.5 | Kodlama ajanları ve pitch-writer |
| Haiku 5.5 | Keşif, test ve doküman ajanları |

- **Varsayılan:** Tanımsız alt ajanlar `CLAUDE_CODE_SUBAGENT_MODEL=sonnet` ile Sonnet'te çalışır.
- **Yükseltme:** İki başarısızlıktan sonra aynı ajan bir kez Opus ile çağrılır.
- **Not:** `CLAUDE_CODE_EFFORT_LEVEL` ortam değişkeni KULLANILMAZ. Bu değişken alt ajanların kendi effort ayarlarını ezer.
