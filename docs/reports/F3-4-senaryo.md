# F3-4: Önleyici kesinti senaryosu (29 Haziran 2025)

- **Model:** claude-opus-5-5 (Opus 5.5), risk-modeler
- **Tarih:** 2026-10-31
- **AOI:** `izmir_menderes`: 925 segment, 17 OSM hattı (way), 92,4 km.
- **Kararlar:** ADR-012 (senaryo günü ve spec §6'da açık kalanlar), docs/DECISIONS.md.
- **Kod:** `src/hatkalkani/model/scenario.py` (`compute_scenario`), testler `tests/model/test_scenario.py` (19 test, sentetik).
- **Tablolar:** `uv run python notebooks/f3_34_tables.py`

> Bu bir **vekil hesaptır**, gerçek kesinti planı değildir. OSM hatlarının çoğu iletim hattıdır (uzunluğun %99,5'i `power=line`, %66'sı ≥154 kV etiketli). Gerçek kesinti birimi EDAŞ fideri ve anahtarlanabilir bölümüdür. Bina sayısı, etkilenen müşteri sayısının vekilidir.

## Özet
- **Seçilen gün: 2025-06-29.** Segmentlerin kullandığı hücrelerde günlük en yüksek hamle 83,5 km/s, medyan 70,6 km/s. Izgaranın tamamında en yüksek değer 86,4 km/s (24,0 m/s) ama bu hücre hiçbir segmente en yakın değil. 29 Haziran her ölçütte birinci.
- **Varsayılan parametreler** (config `scenario`): hamle eşiği 50 km/s, `min_tier` = yuksek. Risk haritası `as_of_used` = 2025-05-31, yani günden önceki son harita.
- **Sonuç (29 Haz, varsayılan):**

  | | Hat km | Bina (≤300 m) | Risk payı | Hat (way) |
  |---|---|---|---|---|
  | (A) İlçe geneli | 92,4 | 3469 | 1,000 | 17 |
  | (B) Hedefli (way birimi, spec) | 83,4 (%90) | 3032 (%87) | 0,917 | 10 |
  | Duyarlılık: birim = aday segment | 18,5 (%20) | 993 (%29) | 0,260 | – |

- **Ana bulgu:** 29 Haziran'da tüm segmentler 63 km/s üstünde. Bu yüzden aday kümesini yalnız kademe belirliyor: 185 kritik+yüksek segment. Ancak bu segmentler 17 hattın 10'unda dağınık. Kesinti birimi OSM way olduğu için hedefli kesinti, ilçe genelinin %90'ına eşit oluyor. Bu sonuç modelin değil birimin sınırıdır: OSM way'leri uzun iletim hatlarıdır (en uzunu 16,5 km). Fider veya anahtarlanabilir bölüm verisiyle kesilen uzunluk 18,5 km'ye kadar inebilir. Bu bir alt sınırdır ve şebeke topolojisi bilinmeden iddia edilmez.
- **Süre:** `compute_scenario` soğuk 374 ms, sıcak 3,5 ms ortalama (en yavaş 22 ms; 15 parametre bileşimi). API'de ilk istek ~1,1 s sürüyor, çünkü modül ilk istekte içe aktarılıyor. Sonraki istekler 18 ms.
- **Tekrarlanabilirlik:** `--stage scenario` iki kez çalıştı; iki dosyanın sha256 değeri aynı.

## Aday günler (scenario_dates.json)

| Gün | En yüksek hamle (segment hücreleri) | Medyan | Izgara en yüksek | 50 km/s üstü segment |
|---|---|---|---|---|
| 2025-06-27 | 54,7 | 40,3 | 54,7 | 34 |
| 2025-06-28 | 71,3 | 53,6 | 71,3 | 790 |
| **2025-06-29** | **83,5** | **70,6** | 86,4 | 925 |
| 2025-06-30 | 62,3 | 52,6 | 70,2 | 925 |

Kaynak: Open-Meteo arşivi `wind_gusts_10m`, yerel günün saatlik değerlerinin en büyüğü; her gün her hücre için 24 saat var. Seçim kuralı ADR-012 madde 1'dedir.

## Duyarlılık: hamle eşiği × min_tier (29 Haziran 2025)
Spec ±10 km/s istiyor (40/50/60). 70 ve 80 km/s, eşiğin etkili olduğu aralığı göstermek için eklendi (genişletilmiş aralık). "Seg." sütunları, birimi yalnız aday segment alan duyarlılık varyantıdır.

| min_tier | Eşik km/s | Aday segment | Hat | Hat km | km payı | Bina | Bina payı | Risk payı | Seg. km | Seg. bina | Seg. risk payı |
|---|---|---|---|---|---|---|---|---|---|---|---|
| kritik | 40 / 50 / 60 | 46 | 9 | 82,0 | 0,887 | 3024 | 0,872 | 0,900 | 4,6 | 293 | 0,071 |
| kritik | 70 | 40 | 6 | 41,4 | 0,447 | 1110 | 0,320 | 0,469 | 4,0 | 127 | 0,062 |
| kritik | 80 | 4 | 1 | 3,4 | 0,037 | 17 | 0,005 | 0,042 | 0,4 | 11 | 0,006 |
| yuksek | 40 / 50 / 60 | 185 | 10 | 83,4 | 0,902 | 3032 | 0,874 | 0,917 | 18,5 | 993 | 0,260 |
| yuksek | 70 | 118 | 8 | 59,2 | 0,641 | 1490 | 0,430 | 0,669 | 11,8 | 328 | 0,169 |
| yuksek | 80 | 14 | 1 | 3,4 | 0,037 | 17 | 0,005 | 0,042 | 1,4 | 13 | 0,020 |
| orta | 40 / 50 / 60 | 463 | 17 | 92,4 | 1,000 | 3469 | 1,000 | 1,000 | 46,2 | 2481 | 0,591 |
| orta | 70 | 267 | 11 | 63,2 | 0,684 | 1513 | 0,436 | 0,705 | 26,6 | 774 | 0,346 |
| orta | 80 | 26 | 1 | 3,4 | 0,037 | 17 | 0,005 | 0,042 | 2,6 | 17 | 0,034 |

Karşılaştırma için 28 Haziran (en yüksek 71,3 km/s), `yuksek`: 40 ve 50 km/s'de 83,4 km; 60 km/s'de 31 aday, 2 hat, 15,7 km, 118 bina, risk payı 0,188; 70 km/s'de 3,4 km; 80 km/s'de aday yok. Eşik ±10 km/s, rüzgârın segmentler arasında değiştiği günlerde sonucu belirgin biçimde değiştirir. 29 Haziran ise 40–60 km/s aralığında eşiğe duyarsızdır.

## Yöntem (ADR-012)
- **Rüzgâr:** m/s × 3,6 = km/s. Segment, orta noktasına en yakın Open-Meteo hücresini alır (ADR-009 D5 ile aynı). Gün, Europe/Istanbul yerel takvim günüdür.
- **Aday:** hamle > eşik (kesin büyük) ve kademe ≥ `min_tier`.
- **Hedefli kesinti:** aday içeren her OSM way'in AOI içindeki tüm segmentleri.
- **Bina:** Overture temsil noktası, kesilen segmente ≤ 300 m; her bina bir kez.
- **Risk payı:** uzunluk ağırlıklı Σ risk·uzunluk oranı.
- **API sözleşmesi (ARCHITECTURE v0.2):**
  - Zorunlu alanların hepsi var.
  - Ek alanlar: `district_wide.n_lines/n_segments`, `targeted.n_lines/n_segments/n_candidate_segments/share_line_km/share_buildings`, `wind{...}`, `sensitivity_segment_unit{...}`.
  - Segment özelliklerinde `gust_kmh` ve `candidate` var.
- **Hatalar:** girdi yoksa FileNotFoundError (503), hatalı tarih/eşik/kademe, rüzgârı olmayan gün veya öncesinde harita olmayan gün için ValueError (422).

## Sınırlar
- Open-Meteo ızgarası ~10 km'dir; segmentler yalnız 10 hücre kullanır. Vadi ve sırt ölçeğindeki rüzgâr farkı yakalanmaz.
- Bina sayısı müşteri (abone) sayısı değildir. İletim hattı kesintisinin etkilediği müşteriler hattın 300 m çevresiyle sınırlı değildir.
- OSM'de dağıtım (OG/AG) hattı yok denecek kadar azdır. Bu yüzden senaryo dağıtım şebekesi için sonuç vermez (ADR-007).
- Risk payı göreli skorların toplamıdır, olasılık değildir.

## Sonraki adım önerisi
- GDZ/EDAŞ fider ve anahtar verisi gelince kesinti birimini fider bölümüne çevirmek. Kod bunun için `line_id` yerine bir bölüm kimliğine ihtiyaç duyar.
- API açılışında `compute_scenario` bir kez çağrılmalı (ısıtma). Böylece ilk istek de 500 ms'nin altında kalır.
