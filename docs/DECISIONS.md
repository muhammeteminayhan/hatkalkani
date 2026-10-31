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
  - Menderes'in 4 karosunda örneklenen tarihler 2016-07-22 ile 2020-02-19 arasında. CHM-DATE'in tam sayımına göre geçerli aralık: segment tarihleri 2016-07-22…2020-02-18 (925/925 segment).
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

## ADR-012 — Önleyici kesinti senaryosu: senaryo günü ve spec §6'da açık kalanlar  (2026-10-31, risk-modeler — F3-4)
- **Bağlam:** Spec §6 şunları açık bırakıyor: rüzgârın segmente atanması, "eşiği aşan"ın eşitlik kuralı, gün sınırı, hangi risk haritasının kullanılacağı, bina sayımı, risk payının ağırlığı ve senaryo gününün seçim ölçütü.
- **Karar:**
  1. **Senaryo günü: 2025-06-29.** Kural: `demo.scenario_date_candidates` içinden, segmentlerin kullandığı Open-Meteo hücrelerinde günlük en yüksek saatlik hamlesi en büyük olan gün; eşitlikte segment medyanı, sonra erken tarih. Değerler (km/s, segment hücreleri; parantezde medyan): 27 Haz 54,7 (40,3) · 28 Haz 71,3 (53,6) · **29 Haz 83,5 (70,6)** · 30 Haz 62,3 (52,6). 29 Haziran her ölçütte birinci; tüm ızgaradaki en yüksek değer de bu gündedir (86,4 km/s = 24,0 m/s, F2-5'in önerisi, ama hiçbir segmentin en yakın hücresi değil). Gün, 29.06.2025 Menderes yangını ve GDZ'nin 27–30 Haziran kesinti penceresiyle örtüşür (ADR-006).
  2. **Rüzgâr:** wind_hourly.parquet m/s × 3,6 = km/s. Segment, orta noktasına en yakın hücreyi alır; yinelenen hücreler ADR-009 D5'teki gibi birleştirilir. Gün, Europe/Istanbul yerel takvim günüdür (ADR-009). Değer, o günün saatlik `wind_gusts_10m` en büyüğüdür. Topoğrafik çarpan uygulanmaz: spec ham hamle diyor ve topoğrafya skorda wind_exposure olarak zaten var.
  3. **Aday:** hamle > eşik (kesin büyük; "aşan") VE kademe ≥ `min_tier`. Rüzgâr verisi olmayan segment aday olmaz.
  4. **Risk haritası:** tarihten kesin önceki en son as_of (`inputs.as_of_used`), yani o günün sabahı elde olan harita. 2025-06-29 için 2025-05-31.
  5. **Kesinti birimi:** aday içeren OSM way'in (`line_id`) AOI içindeki tüm segmentleri kesilir. `segments` alanı kesilen hatların segmentleridir; `/api/segments` özelliklerine ek olarak `gust_kmh` ve `candidate` taşır.
  6. **Bina:** Overture binasının temsil noktası (wui_exposure ile aynı) kesilen bir segmente ≤ `buffers_m.affected_building` (300 m, dahil) ise sayılır; her bina bir kez. Bina dosyası ilçe sınırı + 500 m tampondur; sınır dışında kalan ama hatta yakın binalar da sayılır.
  7. **Risk payı:** uzunluk ağırlıklıdır: Σ risk·uzunluk (B) / Σ risk·uzunluk (A).
  8. **Duyarlılık:** Birimi yalnız aday segment alan varyant (`sensitivity_segment_unit`; anahtarlanabilir bölüm varsayımı, alt sınır). Eşik × min_tier tablosu docs/reports/F3-4-senaryo.md'dedir.
  9. **Hata türleri:** girdi dosyası yoksa FileNotFoundError (API 503), hatalı istekte ValueError (API 422). Statik girdiler önbellektedir ve dosya imzası (mtime, boyut) değişince yeniden yüklenir.
- **Sonuçlar:** 29 Haziran, 50 km/s, `yuksek`: ilçe geneli 92,4 km ve 3469 bina; hedefli 83,4 km (%90) ve 3032 bina (%87), risk payı 0,917, 17 hattın 10'u. Bu gün tüm segmentler 63 km/s üstünde olduğundan aday kümesi kademeyle belirlenir. OSM way'leri uzun iletim hatları olduğu için hedefli kesinti neredeyse ilçe geneline eşittir. Segment birimiyle 18,5 km, 993 bina, risk payı 0,260 çıkar. Gerçek kazancı ölçmek için EDAŞ fider verisi gerekir.
- **Ödünleşimler:** ~10 km'lik Open-Meteo ızgarasında segmentler yalnız 10 hücre kullanır; yerel rüzgâr farkı yakalanmaz. Sabitler (3,6; kesin büyük; uzunluk ağırlığı) kodda adlandırılmış sabitlerdir.

## ADR-013 — Geriye dönük test protokolü (sonuç görülmeden kayıtlı) ve FIRMS `type` filtresi  (2026-10-31, risk-modeler — F3-3; `type` filtresi orkestratör kararı)
- **Bağlam:** Spec §5 olay tanımını (kümeleme, tutuşma vekili, olay evreni), "beklenen pay"ı, güven aralığını ve taban çizgilerinin hesabını açık bırakıyor. F2-5b, FIRMS'e `type` sütununu ekledi. Bu kayıt, backtest gerçek veride hesaplanmadan önce yazıldı; eşik ve parametreler sonuca göre değiştirilmeyecek.
- **Karar:**
  1. **FIRMS `type` (orkestratör kararı, tanım düzeltmesi):** fire_history ve olay kümelerinde yalnız `type` 0 (varsayılan bitki örtüsü yangını) ve `type`'ı boş satırlar kullanılır; 1 (volkan), 2 (statik kara kaynağı) ve 3 (deniz) dışlanır. Boş `type` yalnız NRT satırlarındadır (VIIRS'te 2026-08-27…2026-10-21 arası 13 satır); bunlar tutulur ve meta veride sayılır. Etki: VIIRS'te yalnız 6 deniz tespiti (2016–2024) düştü; statik kaynakların (185) hepsi MODIS'tedir ve zaten kullanılmıyordu.
  2. **Olaylar:** `periods.backtest_season` yerel günleri (2025-06-01…2025-09-30, ADR-009 gün kuralı) içindeki VIIRS (S-NPP, NOAA-20; SP ve NRT) tespitleri, 1. maddedeki filtreyle.
  3. **Kümeleme:** tek bağlantılı uzay-zaman kümeleme. İki tespit, metrik CRS'de ≤ `backtest.cluster_distance_m` (1000 m) ve yerel gün farkı ≤ `backtest.cluster_gap_days` (2) ise bağlanır. Tutuşma vekili, kümenin ilk geçişindeki (en erken zaman damgası) tespitlerin ağırlık merkezidir.
  4. **Olay evreni:** tutuşma vekili ilçe sınırı içinde olan kümeler (`n_events_total`). Sınır dışında kalan ama hatta yakın kümeler yalnız tanı amaçlı sayılır.
  5. **Hat yakını (birincil):** vekilin en yakın segmente uzaklığı ≤ `buffers_m.event_line_distance` (500 m). 1000 ve 2000 m YALNIZ etiketli duyarlılık analizidir.
  6. **Metrik:** her hat yakını olay için en yakın segmentin `risk_pct` değeri (ADR-010 orta-sıra yüzdeliği). Üst %10: `risk_pct` ≥ 0,90; üst %20: ≥ 0,80. `expected` = bu kümedeki segmentlerin sayıca payı; `lift` = pay / expected. `ci95`: olaylar üzerinde yüzdelik bootstrap (B = 10000, tohum 20250531). Küçük örneklem için Clopper–Pearson aralığı ve tek yönlü binom p değeri de verilir.
  7. **Taban çizgileri** (aynı olaylar, aynı bootstrap örnekleri): `expected` (rastgele segment; Monte Carlo sıfır dağılımı), `length` (uzunluğa orantılı rastgele), `vegetation_chm` (yalnız CHM: vegetation_encroachment), `tree_shrub_cover` (yalnız WorldCover ağaç+çalı: fuel_continuity, spec b), `buildings` (yalnız bina yakınlığı: wui_exposure, spec c), `fire_history` (yalnız geçmiş yangın), `linear` (aynı ağırlıklar, doğrusal birleştirme). Her taban çizgisi kendi orta-sıra yüzdeliği ve kendi `expected` değeriyle ölçülür.
  8. **Ek duyarlılık (etiketli):** strike_trees yerine `aux_strike_tall_clusters` ile skor (F3-1 O8 bulgusu).
  9. **Sızıntı korumaları:** risk dosyasının as_of'u `periods.backtest_asof` olmalı; özellik meta verisindeki her `max_time_used_utc` as_of kesiminden önce olmalı; kesim sezon başından sonra olamaz. Aksi halde backtest hata verir.
  10. **Parametreler:** config/risk_weights.yaml → `backtest` (yeni blok).
- **Ödünleşimler:** Kümeleme zinciri büyük yangınları tek olaya indirir; küçük ve kısa yangınlar ayrı olay sayılır. Sayıca `expected`, uzunluğu farklı segmentlerde küçük bir sapma yaratır; bu yüzden `length` taban çizgisi ayrıca verilir.
- **Sonuçlar (protokol kaydından sonra hesaplandı; hiçbir parametre değiştirilmedi):**
  - Sezonda 788 VIIRS tespiti, 36 küme. Vekili ilçe içinde olan 10 olay; bunların 2'si hatta ≤500 m.
  - Üst %10 ve üst %20 payı 0/2, lift 0. Bootstrap aralığı k = 0 olduğu için dejenere ([0, 0]). Kesin binom lift aralığı üst %10 için [0; 8,37], üst %20 için [0; 4,21]. Test bilgi vermiyor.
  - Taban çizgileri de ayrışmıyor (yalnız bina yakınlığı 1/2 ve 2/2; n = 2, 14 karşılaştırma). 2000 m duyarlılığında n = 5, model 0/5. strike_tall varyantı da 0; O8 için tanım değişmedi.
  - 29.06.2025 vakası (E2025_010, 441 tespit): vekil en yakın OSM hattına 2611 m, ilçe sınırının 263 m dışında. Hiçbir eşikte hat yakını değil.
  - Skora etki (F2-5b yeniden ingest'i, FIRMS uzatması ve `type` filtresi birlikte; F3-2 sürümüne göre): backtest haritasında Spearman 1,0000 (en büyük |Δrisk| 0,33), güncel haritada 0,9999 (0,90). İki haritada da kritik küme aynı.
  - Ayrıntı: docs/reports/F3-3-backtest.md. İyileştirme önce EDAŞ dağıtım hattı verisi, sonra çok yıllı (2016–2024) kayan backtest; ikisi de yeni bir protokol kaydı gerektirir.
- **Ek not (FIX-F3, 2026-10-31, risk-modeler; REV-F3F4 Y1, O2, O4, D2):** Yalnız ekleme; yukarıdaki metin değiştirilmedi. Skor, ağırlık, kademe ve protokol parametreleri değişmedi; risk_*.parquet sha256 aynı.
  - **Kayıt ifadesi (D2):** Başlıktaki ve bağlamdaki "sonuç görülmeden kayıtlı" ifadesi depodan doğrulanamaz.
    - Doğrulanabilen: 500 m birincil eşik ilk iskelet commit'inden (c423a81) beri config/aoi.yaml'da sabit. FIRMS `type` filtresi 2025 sezonunda 0 tespit dışladı (fire_history'den yalnız 6 deniz tespiti düştü).
    - Doğrulanamayan: ADR-013, `backtest` config bloğu, `type` filtresi, kod ve sonuç raporu aynı commit'te (abe3ebb) kaydedildi.
    - İleride protokol, sonuçtan önce ayrı bir commit veya etiketle kaydedilecek.
  - **Statik katman beyanı (Y1):** 9. maddedeki koruma yalnız zaman damgalı veriyi denetliyordu; statik katmanlar sessizce geçiyordu.
    - `check_no_leakage` artık statik katmanları ayrı bir listede toplar. Ölçüt: `temporal_status` "after_" içerir, ya da sürüm, erişim (MANIFEST `tarih`) veya görüntü tarihi ≥ as_of'tur. Tarihi bilinmeyen hat, sınır ve CHM katmanları da beyan edilir.
    - Bu katmanlar hata vermez (as_of tarihli bir anlık görüntü yok). backtest.json'da `leakage.static_after_as_of` alanına ve sınırlılıklara yazılır.
    - 2025-05-31 haritası: binalar (Overture 2026-10-21.0; wui_exposure ve bina yakınlığı taban çizgisi), hatlar/segmentler ve ilçe sınırı (OSM, erişim 2026-10-30). Etkisi ölçülmedi; bina yakınlığı taban çizgisi iyimser olabilir.
  - **Dejenere aralık (O2):** k ∈ {0, n} iken bootstrap aralığı tek noktaya çöker. Bu durumda `ci95: null` ve `ci95_note: "degenerate"` yazılır; Clopper–Pearson aralığı (`ci95_binomial`) korunur. backtest.json'da `ci95`, tam olarak `ci95_note` dolu olduğunda null'dır.
  - **Karar alanı:** `verdict.informative` = (hat yakını olay sayısı ≥ `MIN_EVENTS_INFORMATIVE` = 38).
    - Gerekçe: n ≥ 38'den itibaren tek yönlü kesin binom testi (α = 0,05) üst %20 kümesinde lift 2'yi (pay 0,40'a karşı 0,20) en az %80 güçle saptar. Kesin binom gücü n'ye göre testere dişi çizdiği için gücün bir daha 0,80'in altına düşmediği ilk n alındı (ilk kez 35'te aşılıyor).
    - Eşik, 2025 sonucundan bağımsız bir güç hesabıdır. 2025 sezonunda n = 2 olduğundan makul her eşikte karar "bilgi vermiyor"dur.
  - **Seçim yanlılığı (O4):** Pilot ilçe ve senaryo günleri 2025 yangını yüzünden seçildi (ADR-006, ADR-012); bu backtest aynı sezonu kullanıyor. Çok yıllı testte 2025 ayrı raporlanacak.

## ADR-014 — K2: risk modeli v0.1 kabulü  (2026-10-31, kullanıcı — K2)
- **Karar:** Kural tabanlı risk modeli v0.1, F3 sonuçlarıyla prototip ve başvuru için kabul edildi. Kullanıcının yanıtı: "Onayla, devam et". Sonuçlar: kademeler 46 / 139 / 278 / 462 (göreli), ağırlıklar ±%20 oynatıldığında Spearman ≥ 0,995, 76 iş paketi, 2025-06-29 kesinti senaryosu.
- **Backtest:** 2025 sezonu bilgi vermiyor. Hatta 500 m içinde 2 olay var; karar için en az 38 olay gerekir (`backtest.json → verdict`). Sonuç olduğu gibi raporlanır; modeli ne doğrular ne çürütür.
- **Seçilmeyen seçenek:** 2020–2024 çok yıllı backtest şimdi eklenmedi. Sızıntısız bir çok yıllı test as_of ≥ 2020-03 ister, çünkü CHM görüntüleri 2020-02-18'e kadar uzanıyor (ADR-008).
- **Sonuç:** F3 kapanır. Ağırlık ve eşikler config'te parametre olarak kalır; saha görüşmeleri ve EDAŞ hat verisiyle yeniden değerlendirilecek.
