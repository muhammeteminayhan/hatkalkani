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

## ADR-006 — Pilot ilçe: Menderes  (2026-10-30, kullanıcı — K1)
- **Bağlam:** F1-1, F1-1b ve F1-3 beş adayı karşılaştırdı: Menderes, Çeşme, Ödemiş, Seferihisar, Torbalı (docs/reports/F1-1-aday-ilceler.md, F1-1b-ortu.md, F1-3-vakalar.md).
- **Karar:** Pilot `izmir_menderes`. İlçe sınırıyla kırpılmış havai hat 92 km (≥154 kV 61 km, etiketsiz 31 km); ±30 m koridorda ağaç+çalı %52,6; ~920 segment.
- **Gerekçe:** 29.06.2025 yangını, GDZ'nin önleyici kesinti penceresine (27–30 Haziran) düşüyor. 2024–25'te 2 büyük yangın oldu. Koridorda bitki örtüsü yüksek, işlem yükü küçük.
- **Ödünleşimler:** Hatların üçte ikisi iletim hattı. Yangının hat kaynaklı olduğu yalnızca bildirildi; resmî tespit yok ve itfaiye raporunun değiştirildiği de haberlerde geçiyor. Sunumda "bildirildi" dili kullanılır.
- **Seçilmeyenler:** Menderes + Seferihisar (iki ilçeli AOI; ileride genişleme seçeneği), Çeşme (koridor %24,8), Ödemiş (%24,3), Torbalı (yangın gerekçesi zayıf).

## ADR-007 — Hat verisi: OSM + EDAŞ dosyası  (2026-10-30, kullanıcı — K1)
- **Bağlam:** OSM'de orta gerilim dağıtım hattı neredeyse yok. 33–36 kV etiketli hat yalnızca Torbalı'da var (4 km), Menderes'te hiç yok. Müşteri ise EDAŞ.
- **Karar:** Pilot, OSM havai hatlarıyla (power=line, minor_line) kurulur; her hat kaynağı ve gerilim sınıfıyla etiketlenir. Ingest, EDAŞ'ın GIS dosyasını (data/manual/edas/) aynı şemayla kabul eder ve dosya varsa onu kullanır. GDZ Elektrik'ten örnek veri istenir (MANUAL_TASKS 15).
- **Sonuçlar:** Demoda haritanın hangi hatları gösterdiği açıkça yazılır ("OSM: çoğu iletim hattı"). Yöntem şebekeden bağımsız anlatılır; dağıtım şebekesi için sonuç iddia edilmez.

## ADR-008 — Ağaç yüksekliği kaynağı: CHM v2  (2026-10-30, data-engineer önerisi, orkestratör onayı — F2-3)
- **Bağlam:** CHM v1 karoları şerit bloklu (65536×1); bu yüzden ±30 m koridoru okumak çok veri çekiyor. v2 karoları 512 px döşemeli COG ve model daha yeni.
- **Karar:** Koridor istatistikleri v2'den (`dinov3_global_chm_v2_ml3`) çıkarılır: 4 karo, ≈8 MB pencereli okuma.
- **Ödünleşimler:** v2'de görüntü tarihi yok. v1 tarihleri (Menderes için 2016-07-22..2020-02-19) yalnızca referans. MODEL_CARD'a "CHM taban yılı bilinmiyor" yazılır. Piksel değerinin uint8 metre olduğu varsayımı F2 incelemesinde doğrulanır.

## ADR-009 — Özellik katmanı: as_of kuralı ve spec'te açık kalan tanımlar  (2026-10-31, risk-modeler — F3-1)
- **Bağlam:** Spec §2 as_of sonrası veriyi yasaklıyor. Ancak gün sınırını (UTC mi yerel mi), FIRMS geçmiş penceresinin sonunu, S2 kompozit seçimini ve bazı hesap ayrıntılarını tanımlamıyor (REV-F2: O3, O10, D1, D5).
- **Karar:**
  1. **Gün sınırı:** as_of, Europe/Istanbul yerel takvim günüdür ve o gün dahildir. Kesim (hariç) as_of+1 günü 00:00 yerel saattir; 2016'dan beri bu, as_of günü 21:00 UTC'ye denk gelir. Zaman karşılaştırmaları saat dilimli yapılır, saat dilimsiz damga reddedilir. Aynı tanım F3-3 olaylarında ve F3-4 senaryo gününde de kullanılır.
  2. **fire_history:** Pencere, `periods.firms_history[0]` yerel gün başından as_of kesimine kadardır. `firms_history[1]` pencere sonu olarak kullanılmaz: spec "as_of'tan önceki tespitler" diyor ve güncel harita 2025 sezonunu geçmiş saymalı. Yalnız VIIRS kullanılır (S-NPP ve NOAA-20; MODIS dışarıda). Her (yerel gün, 375 m hücre) için tek tespit sayılır. Yoğunluk quartic çekirdekle (bant genişliği `buffers_m.history_kernel`) segment orta noktasında hesaplanır; birim hücre-gün/km².
  3. **fuel_dryness:** Penceresi as_of günü ya da öncesinde biten ve tüm sahneleri kesimden önce olan en son S2 kompoziti seçilir. Sahne tarihlerini kanıtlamak için `s2_meta.json` zorunludur. WorldCover'da su (80) olan pikselle çakışan S2 pikselleri dışlanır (D1). Ters yüzdelik F3-2'de alınır (`direction=lower`).
  4. **wind_exposure:** Yalnız `wind_climatology_summers` yıllarının Haziran–Eylül saatleri (yerel takvim) ve kesimden önceki kayıtlar kullanılır. Yinelenen Open-Meteo hücreleri (lat, lon) ile birleştirilir (D5). Her segment en yakın hücrenin hamle p95 değerini alır. Çarpan 0,5 + segment TPI'sinin AOI içindeki TPI piksellerine göre orta-sıra yüzdeliğidir (0,5–1,5).
  5. **Geometri:** Spec'te "±" ile verilen ölçüler (dryness, slope, CHM) düz uçlu koridor, "tampon" denenler (fuel, wui) yuvarlak tampon olarak uygulanır.
  6. **Statik katmanlar:** CHM, WorldCover 2021, DEM, Overture binaları ve OSM hatları as_of ile filtrelenemez; zaman durumları metaveride ve F3-1 raporunda yazılır. `asset_condition` için veri yok; sütun tamamen NaN ve `unavailable` olarak işaretli.
  7. **Çalışma anı korumaları:** Zamana göre filtrelenen her faktör `max_time_used_utc` bildirir; bu değer kesimi aşarsa build `TemporalLeakageError` ile durur. Nedeni yazılmamış bir NaN da build'i durdurur.
- **Ödünleşimler:**
  - VIIRS'le sınırlamak ve tekilleştirmek, NOAA-20'nin 2018 öncesinde olmamasından gelen zaman dengesizliğini azaltır. Ama MODIS'in yakaladığı bazı küçük yangınlar kaçabilir.
  - Su maskesi kıyıdaki karışık pikselleri de dışlar.
  - TPI yüzdeliği AOI'ye görelidir; başka bir AOI'de çarpanlar yeniden ölçeklenir.
  - Spec sabitleri (Haz–Eyl, p95, 0,5–1,5, 375 m, WorldCover sınıfları) şimdilik kodda adlandırılmış sabitlerdir. Config'e taşınmaları orkestratör onayına bağlıdır.
  - Ayrıntı ve sayılar: docs/reports/F3-1-ozellikler.md.
