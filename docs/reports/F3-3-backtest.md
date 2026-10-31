# F3-3: Geriye dönük test (as_of 2025-05-31 → 2025 yangın sezonu)

- **Model:** claude-opus-5-5 (Opus 5.5), risk-modeler
- **Tarih:** 2026-10-31
- **Protokol:** ADR-013, sonuçlar görülmeden kaydedildi. Parametreler config/risk_weights.yaml → `backtest`, birincil eşik `buffers_m.event_line_distance` = 500 m.
- **Kod:** `src/hatkalkani/model/backtest.py`, testler `tests/model/test_backtest.py` (9 test, sentetik; sızıntı testi dahil).
- **Çıktılar:** `data/processed/izmir_menderes/backtest.json`, `events_2025.geojson`. İki çalıştırmada sha256 aynı.

## Özet (dürüst sonuç)
- **Test bilgi vermiyor:** Örneklem çok küçük. Sezonda ilçe içinde **10** yangın kümesi var; bunların yalnız **2**'si bir OSM hattına ≤500 m.
- **Sonuç:** İki olayın hiçbiri üst %10 veya üst %20'de değil. **Lift 0** (0/2).
  - Bootstrap aralığı [0, 0]. Bu aralık k = 0 olduğu için dejeneredir ve belirsizliği göstermez.
  - Dürüst aralık kesin binom aralığıdır: lift üst %10 için [0; 8,4], üst %20 için [0; 4,2].
  - Veri "rastgeleden iyi" ile "rastgeleden kötü" arasında ayrım yapamıyor. "Rastgeleden iyi" için tek yönlü p = 1,0. 0/2 sonucu rastgele sıralamada da olasıdır: üst %10 için (1 − 0,1005)² = 0,81, üst %20 için 0,64.
- **Hat yakını olaylar:** İkisi de tek tespitli, çok küçük yangınlar (FRP 1,0 ve 0,4 MW). Nedenleri bilinmiyor; tarla veya anız yakması olabilir (doğrulanmadı).
  - E2025_007: 19 Haz, 34 m, segment yüzdeliği 0,18 (düşük).
  - E2025_035: 18 Eyl, 364 m, yüzdelik 0,65 (orta).
- **Vaka 29.06.2025 Menderes:** FIRMS kümesi 441 tespitli. Tutuşma vekili en yakın OSM hattına **2611 m** uzakta ve ilçenin batı sınırının 263 m dışında (hangi komşu ilçede olduğu veriyle doğrulanmadı). Kümenin hatta en yakın tespiti bile 1285 m. Kayıtlı protokolde bu yangın "hat yakını" sayılmaz; hiçbir eşikte (500/1000/2000 m) sayılmaz.
- **Neden kötü/bilgisiz:**
  1. Az olay.
  2. OSM hatlarının çoğu iletim hattı; hat kaynaklı yangınların çoğunun çıktığı dağıtım (OG/AG) hatları haritada yok.
  3. FIRMS ilk tespiti tutuşmadan saatler sonra ve km ölçeğinde belirsiz.
- **İyileştirme seçenekleri:** aşağıda.

## Olaylar
| Adım | Sayı |
|---|---|
| Sezondaki FIRMS satırı (tüm ürünler) | 941 |
| VIIRS (S-NPP 369 + NOAA-20 419), `type` 0 | 788 (type≠0 yok; NRT yok) |
| Bunların ilçe içindeki | 137 |
| Uzay-zaman kümesi (≤1000 m, ≤2 gün) | 36 |
| Tutuşma vekili ilçe içinde (`n_events_total`) | **10** |
| Sınır dışı ama hatta ≤500 m | 0 (evren kısıtı hat yakını olay kaybettirmedi) |
| Hat yakını ≤500 m (`n_events`, birincil) | **2** |
| ≤1000 m (DUYARLILIK) | 2 |
| ≤2000 m (DUYARLILIK) | 5 |

İlçedeki 10 olay (mesafeden bağımsız, yalnız betimsel): en yakın segment yüzdeliklerinin ortalaması 0,455. Rastgelede beklenen 0,5'tir. Bu bir hat tutuşması testi değildir.

## Metrikler (birincil, 500 m, n = 2)
| | Pay | Beklenen | Lift | Bootstrap %95 | Kesin binom %95 (lift) | p (tek yönlü) |
|---|---|---|---|---|---|---|
| Üst %10 | 0/2 = 0,00 | 0,1005 (uzunluk 0,1006) | 0,00 | [0, 0]* | [0; 8,37] | 1,00 |
| Üst %20 | 0/2 = 0,00 | 0,200 (uzunluk 0,1997) | 0,00 | [0, 0]* | [0; 4,21] | 1,00 |

\* k = 0 olduğunda her bootstrap örneği 0 verir; aralık belirsizliği temsil etmez.

## Taban çizgileri (500 m, aynı 2 olay)
| Anahtar | Tanım | Üst %10 pay / lift | Üst %20 pay / lift |
|---|---|---|---|
| expected | Rastgele segment (sıfır dağılımı) | 0,10 / 1,0 (%95: 0–4,97) | 0,20 / 1,0 (%95: 0–5,0) |
| length | Uzunluğa orantılı rastgele | 0,10 / 1,00 | 0,20 / 1,00 |
| vegetation_chm | Yalnız CHM (hatta yakın yüksek ağaç) | 0 / 0 | 0 / 0 |
| tree_shrub_cover | Yalnız WorldCover ağaç+çalı | 0 / 0 | 0 / 0 |
| buildings | Yalnız bina yakınlığı | 0,5 / 5,0 | 1,0 / 5,0 |
| fire_history | Yalnız geçmiş yangın | 0 / 0 | 0 / 0 |
| linear | Doğrusal birleştirme | 0 / 0 | 0 / 0 |

Bina yakınlığının yüksek lift'i n = 2'de gürültüdür; bootstrap aralığı [0; 10]. Bu sonuç yalnız iki küçük hat yakını yangının yerleşime yakın olduğunu gösterir. Üst %20'deki binom p = 0,04 (2/2), 7 taban çizgisi × 2 kesim = 14 karşılaştırmadan biridir ve Bonferroni eşiğinin (0,05/14 ≈ 0,0036) altında değildir. Model hiçbir taban çizgisini geçmiyor; bu küçük örneklemde yöntemler birbirinden ayrılamıyor.

## DUYARLILIK ANALİZİ (birincil eşik değildir)
- **1000 m:** n = 2. Olaylar aynı, sonuç aynı.
- **2000 m:** n = 5. Model 0/5 (üst %10 ve üst %20). Kesin binom lift aralığı üst %10 için [0; 5,19], üst %20 için [0; 2,61]. Taban çizgileri:
  - vegetation_chm: üst %20'de 1/5,
  - buildings: üst %10'da 1/5, üst %20'de 2/5,
  - fire_history: üst %20'de 1/5.
- **strike_tall varyantı** (strike_trees yerine yalnız ≥4 m kümeler, F3-1 O8): 500, 1000 ve 2000 m'de 0 olay üst kümelerde. Bu veriyle O8 için bir ADR gerekçesi çıkmıyor; tanım değiştirilmedi.

## Vaka incelemesi: 29.06.2025 Menderes
- **Kaynak:** F1-3 I-1. Hat kaynaklı olduğu yalnız basında bildirildi (medyada aktarılan itfaiye raporu: "kısa devre sonucu çıkan kıvılcımların ... kuru otları tutuşturması"). Resmî tespit yok. İzmir Başsavcılığı, GDZ ve kamu görevlileri hakkındaki suç duyurusunda "soruşturma yapılmasına yer olmadığına" karar verdi (haber 15.08.2026; F1-3 §1).
- **FIRMS kümesi:** E2025_010. 441 tespit (81'i ilçe içinde), 29 Haz–1 Tem.
  - İlk geçiş: 29 Haz 10:14 UTC (13:14 yerel). Bu geçişte zaten 14 piksel yanıyordu; tutuşma daha erkendi ve yeri km ölçeğinde belirsiz.
- **Tutuşma vekili:** 38,17974 K, 26,98138 D (ilk geçiş tespitlerinin ağırlık merkezi). İlçenin batı sınırının 263 m dışında; bu yüzden olay evrenine (`n_events_total`) girmiyor.
- **Mesafe (metrik CRS):**
  - Vekil → en yakın OSM segmenti (1181160379_0105, orta, yüzdelik 0,714): **2611 m**.
  - İlk geçişin 14 tespiti hatta 1285–4080 m uzakta. Tüm tespitlerin en yakını 1285 m; yalnız %4'ü ≤2 km.
- **Yorum:**
  - OSM'deki hatlar bu yangının kaynağı olarak görünmüyor.
  - Haberdeki kısa devre bir dağıtım hattını (OG/AG) düşündürüyor. Bu hatlar OSM'de yok (ADR-007).
  - Model bu vakada ne doğrulanabilir ne çürütülebilir. Vaka, EDAŞ hat verisinin neden gerekli olduğunu gösteriyor.

## Sızıntı ve tekrarlanabilirlik
- `check_no_leakage` şunları denetler; aksi halde `BacktestLeakageError` verir:
  - risk as_of = `periods.backtest_asof`,
  - özellik meta verisindeki her `max_time_used_utc` < as_of kesimi (2025-05-31 21:00 UTC),
  - kesim ≤ sezon başı.
- Sentetik test, sezon ve sonrası tespitlerin, rüzgârın ve S2'nin eklenip her şeyin yeniden kurulduğu durumu dener. Olay sayısı değişiyor, ama hiçbir segmentin as_of yüzdeliği değişmiyor (`test_season_detections_never_move_the_as_of_ranking`).
- Gerçek veride backtest haritasının özellikleri: fire_history `max_time_used_utc` 2025-05-28 11:54 UTC; S2 kompoziti 2025-04-15…05-31 (24 sahne); rüzgâr klimatolojisi 2022–2024.

## Skor haritası özetleri (F2-5b + `type` filtresi sonrası, yeniden üretildi)
Segment sayısı (uzunluk). Son sütun, F3-2 sürümüyle karşılaştırmadır; F2-5b yeniden ingest'i, FIRMS uzatması ve `type` filtresinin toplam etkisini gösterir.

| as_of | kritik | yüksek | orta | düşük | Skor min / medyan / max | F3-2 sürümüyle Spearman (en büyük \|Δrisk\|) |
|---|---|---|---|---|---|---|
| 2025-05-31 | 46 (4,6 km) | 139 (13,9 km) | 278 (27,7 km) | 462 (46,3 km) | 16,5 / 48,8 / 78,9 | 1,0000 (0,33); kritik küme aynı |
| 2026-10-30 | 46 (4,6 km) | 139 (13,8 km) | 278 (27,8 km) | 462 (46,2 km) | 19,3 / 49,0 / 77,6 | 0,9999 (0,90); kritik küme aynı |

`type` filtresi VIIRS'te yalnız 6 deniz tespitini (2016–2024) düşürdü. Güncel haritada FIRMS boşluğu 0 gün (F3-1'de 395 gündü). 13 NRT satırı `type`'sız tutuldu.

## İyileştirme seçenekleri (öncelik sırasıyla)
1. **EDAŞ/GDZ dağıtım hattı verisi:** "Hat yakını olay" ancak o zaman hat kaynaklı yangınları temsil eder. Ingest bu dosyayı zaten kabul ediyor (ADR-007).
2. **Çok yıllı kayan backtest:** 2016–2024 için her yıl as_of = 31 Mayıs ve sezon Haz–Eyl. Böylece 9 sezon eklenir; yıllık olay sayısı değişkendir. Her yıl için bahar S2 kompoziti gerekir (data-engineer). Özellik kodu as_of'a göre çalışıyor.
3. **AOI'yi büyütmek** (Menderes + Seferihisar, ADR-006'daki seçenek): 29.06 yangınının vekili ilçenin batı sınırının hemen dışında.
4. **Resmî yangın kayıtları** (OGM, itfaiye; neden ve başlangıç noktasıyla): FIRMS'in tutuşma belirsizliğini ortadan kaldırır.
- Bu seçenekler yeni bir protokol gerektirir. Eşik veya ağırlık bu sonuca göre değiştirilmedi.
