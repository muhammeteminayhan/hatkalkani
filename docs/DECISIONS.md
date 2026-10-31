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
- **Düzeltme (2026-10-31, CHM-META):** v2'nin `metadata/<karo>.geojson` dosyalarında her ayak izi için `properties.acq_date` alanı var.
  - Menderes'in 4 karosunda örneklenen tarihler 2016-07-22 ile 2020-02-19 arasında.
  - Karo içinde tarihler mozaik; tek bir görüntü yılı yok. Tam sayım yapılmadı.
  - "Taban yılı bilinmiyor" yerine bu aralık yazılır. Segment bazında tarih ingest'e eklenecek (docs/reports/CHM-META.md).

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

## ADR-010 — Skor katmanı: yüzdelik, NaN politikası, katkı (Shapley) ve iş paketi birleştirme  (2026-10-31, risk-modeler — F3-2)
- **Bağlam:** Spec §3–4 şunları açık bırakıyor: yüzdelikte bağ (eşit değer) kuralı, NaN politikası, geometrik birleştirmede "katkı"nın tanımı, top_factors seçimi, iş paketinde "ardışık" segmentin tanımı ve dosya adları.
- **Karar:**
  1. **Yüzdelik:** Orta-sıra yüzdeliği kullanılır: (altındaki değer sayısı + 0,5 × eşit değer sayısı) / n, yalnız sonlu değerler üzerinden. Bağlı değerler aynı yüzdeliği alır. `direction=lower` olan faktör (fuel_dryness) ters sıralanır. Her faktörün AOI ortalaması tam 0,5'tir; sabit bir faktör 0,5 olur.
  2. **NaN:**
     - `all_water` → 0 (bitki yok, en düşük kuruluk riski; F3-1 önerisi).
     - Belgelenmiş diğer nedenler → 0,5. Bu nötr değerdir, katkısı 0'dır; segment `imputed` sütununda işaretlenir.
     - Nedeni yazılmamış NaN hata verir.
     - `unavailable` bir faktörün ağırlığı 0'dan büyükse hata verir.
  3. **Ağırlıklar:** Her bileşenin ağırlıkları kendi toplamına bölünür. Toplam 1 değilse uyarı yazılır; kullanılan değerler metaveride `weights_effective` alanındadır.
  4. **Katkı:**
     - `contrib_<faktör>`, risk ile referans segmentin riski arasındaki farkın tam Shapley değeridir (2^k koalisyon).
     - Referans segmentte tüm faktörler 0,5 yüzdelikte, riski 50'dir. Katkıların toplamı risk − 50'dir.
     - top_factors, yuvarlanmış katkısı 0'dan büyük olan en fazla 3 faktördür; eşitlikte config sırası geçerlidir.
     - **Gerekçe:** Pay bölüşümünde (w·f, P ve C yarı yarıya) kritik+yüksek 185 segmentin 114'ünde 1. neden en ağır ağırlıklı fuel_continuity çıkıyor ve 1. nedenlerin %6'sının yüzdeliği 0,6'nın altında kalıyor. Shapley'de 1. neden dağılımı çeşitli (enc 78, fuel 71, wui 15, strike 12…) ve bu oran %0.
  5. **Kademe:** Riskin orta-sıra AOI yüzdeliği `tiers` alt sınırıyla karşılaştırılır (≥). Bağlı segmentler aynı kademede kalır. Risk, sıralamadan önce 9 haneye yuvarlanır.
  6. **İş paketi:**
     - Kritik/yüksek segmentler yalnız şu üç koşul birlikte sağlanınca birleşir: aynı `line_id`, ardışık `seq` ve uç uca değme (≤ 1 m). Bu yüzden ilçe sınırında bölünen hat parçaları birleştirilmez; pilotta 6 boşluk var, en küçüğü 12,7 m.
     - `risk_mean` uzunluk ağırlıklıdır.
     - `main_reason`: uzunluk ağırlıklı ortalama katkısı en büyük olan pozitif faktör.
     - `map_url` açıklığın orta noktasını gösterir.
     - Sıralama: risk_max ↓, strike_tree_count ↓, span_id ↑.
  7. **Dosyalar ve alanlar:**
     - Dosya adları as_of eklidir: `risk_<as_of>.{parquet,meta.json,geojson}`, `workorders_<as_of>.{csv,geojson,gpkg}`.
     - `voltage_class`, segments.parquet'teki sınıftır (ge154kv/etiketsiz…). Spec §1'deki lv/mv/hv sınıfı `voltage_level` alanındadır.
     - İş paketlerinde spec §4 alanlarına ek alanlar var: `priority`, `tier_max`, `n_segments`, `segment_ids`, `voltage_level`, `voltage_kv`, `main_reason_key/en`, `reasons_tr/en`, `strike_tall_count`, `as_of`.
     - `risk_<as_of>.geojson` yalnız `/api/segments` özelliklerini taşır; orada top_factors gerçek bir dizidir. Parquet'te top_factors JSON metni olarak saklanır.
- **Ödünleşimler:**
  - Shapley katkısı "ağırlık × yüzdelik" kadar sezgisel değil. Arayüzde "tipik segmente göre +X puan" diye anlatılmalı.
  - Skoru referansın altında olan segmentlerde top_factors 3'ten kısa olabilir; pilotta 5 segmentte boş.
  - Kademeler görelidir: her zaman %5 kritik çıkar ve bu mutlak bir tehlike düzeyi değildir.
  - Sabitler (0,5, all_water → 0, 1 m, 3 neden, doğrusal 0,6/0,4) şimdilik kodda adlandırılmış sabitlerdir. Config'e taşınmaları orkestratör onayına bağlıdır.
  - Ayrıntı: docs/reports/F3-2-skor.md.

## ADR-011 — API sözleşmesi v0.2: as_of seçimi, ilçe sınırı, henüz üretilmemiş çıktılar  (2026-10-31, orkestratör — F4)
- **Bağlam:** Kullanıcı çalışan prototipi 1 Kas sabahına kadar istiyor. API ve arayüz, F3-3 (backtest) ve F3-4 (senaryo) bitmeden paralel yazılacak. Doğrulama sekmesi Mayıs 2025 riskini 2025 sezonu olaylarıyla aynı haritada göstermeli.
- **Karar:**
  1. `/api/aoi`, `/api/segments`, `/api/segments/{id}`, `/api/workorders` ve `/api/workorders/export` isteğe bağlı `as_of=YYYY-MM-DD` alır. Varsayılan `periods.current_asof`; dosyası olmayan tarih 404 döner.
  2. `/api/health` yanıtına `as_ofs` (mevcut `risk_<as_of>.parquet` tarihleri) eklenir.
  3. Yeni `GET /api/aoi/boundary` ilçe sınırını GeoJSON döner (çevrimdışı altlık yedeği).
  4. Backtest ve senaryo dosyaları henüz yoksa ilgili uç nokta 503 ve `{"detail_tr","detail_en"}` döner.
  5. Senaryo istek anında `hatkalkani.model.scenario.compute_scenario(aoi_id, date, gust_kmh, min_tier) -> dict` ile hesaplanır. F3-4 yazar; dönüş biçimi sözleşmedeki gibidir. Dosyalar: `backtest.json`, `events_2025.geojson`, `scenario_dates.json` (data/processed/<aoi>/).
- **Sonuçlar / ödünleşimler:** Arayüz bu dosyalar gelene kadar 503'ü "henüz hesaplanmadı" diye gösterir. Sözleşme ARCHITECTURE.md'de güncellendi.
