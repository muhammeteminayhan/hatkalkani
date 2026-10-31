# Model kartı: HatKalkanı hat–bitki örtüsü yangın riski önceliği

- **Sürüm:** config `risk_weights.yaml` 0.1. Kural tabanlı ilk model (ADR-003).
- **Pilot:** `izmir_menderes`. 17 OSM hattı (way), 925 segment (100 m), 92,4 km.
- **Haritalar:** iki as_of. Geriye dönük test haritası 2025-05-31, güncel harita 2026-10-30.
- **Yazan:** risk-modeler (claude-opus-5-5), 2026-10-31.
- **Kararlar:** ADR-009 (as_of ve özellik tanımları), ADR-010 (skor), ADR-012 (senaryo), ADR-013 (geriye dönük test). Hepsi docs/DECISIONS.md'de.
- **Raporlar:** docs/reports/F3-1-ozellikler.md, F3-2-skor.md, F3-3-backtest.md, F3-4-senaryo.md.

## 1. Amaç ve kullanım sınırı
- **Ne yapar:** Her havai hat segmentine 0–100 arası göreli bir **öncelik** skoru verir. Skor iki bileşenden oluşur:
  - **Tutuşma olasılığı vekili (P):** hatta yakın ağaç, devrilebilecek ağaç, kuruluk, rüzgâra açıklık.
  - **Sonuç / yayılım vekili (C):** yakıt sürekliliği, yerleşime yakınlık, eğim, geçmiş yangın.
- **Ne üretir:** Skordan budama/drone iş paketleri (ardışık kritik+yüksek segmentler) ve önleyici kesinti senaryosu (vekil hesap) üretilir.
- **Çıktı "öncelik"tir, kesin hüküm değildir.** Skor bir yangın olasılığı değildir ve şunlar için kullanılmaz:
  - bir hattın yangına yol açtığını veya açacağını söylemek,
  - yönetmelik ihlali tespit etmek,
  - yangın sorumluluğu belirlemek,
  - kesinti kararını tek başına vermek.
- **Doğru kullanım:** Saha ekibinin bakacağı yerlerin sırasını belirlemek. Her iş paketi sahada gözle doğrulanır; saha bulgusu modele faktör olarak eklenebilir (bir fonksiyon + bir config satırı).
- **Kapsam dışı:** Dağıtım (OG/AG) şebekesi. Etiketli OG hattı yok (0,43 km power=minor_line var; gerilimi varsayımdır) (ADR-007). EDAŞ hat dosyası gelene kadar dağıtım şebekesi için sonuç iddia edilmez.

## 2. Veri ve tarihler
| Veri | Sürüm / dönem | Kullanım | Lisans |
|---|---|---|---|
| OSM havai hatlar ve ilçe sınırı | Overpass, erişim 2026-10-30 (güncel anlık görüntü; backtest as_of'undan sonra). Uzunluğun %99,5'i `power=line`, %66'sı ≥154 kV etiketli | Segmentler | ODbL 1.0 |
| Meta/WRI CHM v2 (`dinov3_global_chm_v2_ml3`) | Görüntü tarihleri 2016-07-22…2020-02-18, mozaik (bkz. §3) | vegetation_encroachment, strike_trees | CC BY 4.0 |
| Sentinel-2 L2A (`sentinel-2-c1-l2a`) | Backtest: 2025-04-15…05-31 (24 sahne). Güncel: 2026-09-15…10-30 (21 sahne, son sahne 10-25) | fuel_dryness (NDMI) | Copernicus açık veri |
| Copernicus DEM GLO-30 | sürüm doğrulanmadı | slope, TPI (wind_exposure) | Copernicus DEM lisansı |
| ESA WorldCover | v200, 2021 | fuel_continuity; su maskesi | CC BY 4.0 |
| Overture binalar | release 2026-10-21.0 (güncel anlık görüntü; backtest as_of'undan sonra); ilçe + 500 m tampon | wui_exposure; senaryoda etkilenen bina | ODbL |
| NASA FIRMS VIIRS (S-NPP, NOAA-20; SP + NRT) | 2015-07-04 → as_of. Güncel haritada son tespit 2026-10-21. MODIS kullanılmaz | fire_history; geriye dönük test olayları | NASA açık veri |
| Open-Meteo arşivi (`wind_gusts_10m`) | Klimatoloji 2022–2024 yazları (Haz–Eyl). Senaryo günleri 2025-06-27…30 | wind_exposure; senaryo | CC BY 4.0 |

- **Zaman kuralı (ADR-009):** as_of, Europe/Istanbul yerel takvim günüdür (dahil). Kesim, ertesi yerel gece yarısıdır (2025-05-31 için 21:00 UTC). Zamanla değişen veriler (FIRMS, Sentinel-2, rüzgâr) kesimden öncedir; bina (Overture 2026-10) ve hat (OSM 2026-10) katmanları güncel anlık görüntüdür.
- **Sızıntı denetimi:** Geriye dönük test, özellik meta verisindeki her `max_time_used_utc` değerini denetler; kesimden sonraki zaman damgalı veri hata verir. Backtest haritasında en geç veri şunlardır:
  - fire_history: 2025-05-28 11:54 UTC,
  - S2: 2025-05-31,
  - rüzgâr: 2024 yazı.
- **Statik katman beyanı (FIX-F3, REV-F3F4 Y1):** Statik katmanların zaman damgası yoktur. as_of'tan önce olduğu gösterilemeyenler hata vermez; `backtest.json` → `leakage.static_after_as_of` alanında ve sınırlılıklarda beyan edilir.
  - Ölçüt: `temporal_status` "after_" içerir ya da sürüm, erişim veya görüntü tarihi as_of'a eşit ya da sonradır. Tarihi bilinmeyen hat, sınır ve CHM katmanları da beyan edilir.
  - 2025-05-31 haritasında beyan edilenler: binalar (Overture 2026-10-21.0; wui_exposure ve bina yakınlığı taban çizgisi), hatlar/segmentler ve ilçe sınırı (OSM, erişim 2026-10-30).
  - Etkileri ölçülmedi. Bina katmanı as_of'taki değil sonraki durumu gösterdiği için bina yakınlığı taban çizgisinin sonucu iyimser olabilir.
- **FIRMS `type` filtresi (ADR-013, orkestratör kararı):** Yalnız `type` 0 ve `type`'ı boş (NRT) satırlar kullanılır; 1/2/3 dışlanır. VIIRS'te bu kuralla yalnız 6 deniz tespiti düştü. Güncel haritada 13 NRT satırı `type`'sız tutuldu.

## 3. Ağaç yüksekliği (CHM) görüntü tarihleri
- **Görüntü aralığı 2016-07-22…2020-02-18.** Kaynak: Menderes'in 4 CHM v2 karosundaki ayak izi tarihleri (CHM-META, ADR-008 düzeltmesi); aralık, segment koridorlarına düşen ayak izlerinden okunur (`chm_acq_segment.meta.json`, risk meta verisi `chm_dates`). Backtest sınırlılık metni de bu alandan üretilir. CHM bir mozaiktir; tek bir görüntü yılı yoktur. (FIX-F3 düzeltmesi: önceki "2020-02-19" değeri v1 referans aralığından geliyordu.)
- **Segment düzeyi:**
  - Her segmentin ±30 m koridorunda alanca baskın görüntü tarihi risk parquet'indedir: `chm_year`, `chm_acq_min`, `chm_acq_max`, `chm_acq_dominant` (kaynak `chm_acq_segment.parquet`). Risk GeoJSON şeması değişmedi.
  - Baskın yıl dağılımı (925 segment): 2016: 30, 2017: 23, 2018: 15, 2019: 630, 2020: 227. Segmentlerin %93'ünde baskın yıl 2019 veya 2020.
- **Sınırlılık:** Ağaç yüksekliği as_of tarihinden 5–9 yıl eski görüntüye dayandığı için büyüme eksik tahmin edilebilir.
  - Kesin aralık backtest haritası (2025-05-31) için 5,3–8,9 yıl, güncel harita (2026-10-30) için 6,7–10,3 yıl.
  - Görüntüden sonra budanan veya kesilen ağaçlar hâlâ yüksek görünebilir.
- **Doğruluk:** v1 için bildirilen hata MAE ~2,8 m'dir (DATA_SOURCES); v2 için ayrı bir değer doğrulanmadı. Bu yüzden tek piksel yerine piksel kümeleri kullanılır (strike_trees: ≥4 px bağlı küme).
- **Değer biçimi:** Piksel değerinin uint8 metre olduğu varsayılır. Bu varsayım çalışma anında profil ve 0–100 m aralığı denetimiyle korunur. Gerçek veride p99 17 m, en büyük değer 32 m (F3-1).

## 4. Faktörler ve ağırlıklar
Ağırlıklar başlangıç varsayımıdır (config başlığı: "BAŞLANGIÇ VARSAYIMLARI"). Sonuçlara bakılarak ayarlanmadı. Geriye dönük test kalibrasyon için yeterli olay vermedi (§7).

| Bileşen | Faktör | Ağırlık | Ham tanım (kısa) | Veri |
|---|---|---|---|---|
| P | vegetation_encroachment | 0,35 | Açıklık bandında ≥4 m CHM piksellerinin oranı | CHM |
| P | strike_trees | 0,25 | ±30 m'de h ≥ d + 1 m koşulunu sağlayan ≥4 px küme sayısı | CHM |
| P | fuel_dryness | 0,25 | ±50 m koridorda NDMI medyanı (düşük = kuru) | Sentinel-2 |
| P | wind_exposure | 0,15 | Hamle p95 × topoğrafik açıklık çarpanı (TPI); etiket "Rüzgâra topoğrafik açıklık" | Open-Meteo, DEM |
| C | fuel_continuity | 0,40 | 1000 m tamponda ağaç + çalı oranı | WorldCover |
| C | wui_exposure | 0,30 | 500 m içinde bina sayısı, log1p | Overture |
| C | slope | 0,20 | ±100 m koridorda ortalama eğim | DEM |
| C | fire_history | 0,10 | as_of öncesi VIIRS tespitlerinin 2 km çekirdek yoğunluğu | FIRMS |
| C | asset_condition | 0,0 | Şirket verisi yok; skora girmez | — |

- **Normalizasyon:** Her faktör AOI içi orta-sıra yüzdeliğine çevrilir (ADR-010).
- **Birleştirme:** `risk = 100·√(P·C)` (geometrik).
- **Açıklama:** `top_factors`, Shapley katkılarına dayanır. Referans, tüm faktörlerin 0,5 olduğu durumdur (risk 50). Skoru en çok yukarı çeken en fazla 3 faktör gösterilir.
- **Faktör notları:**
  - **wind_exposure** fiilen bir topoğrafya faktörüdür. TPI çarpanıyla ρ = 0,984, hamleyle ρ = 0,008 (F3-1). Bu yüzden etiketi "Rüzgâra topoğrafik açıklık" oldu. Open-Meteo ızgarası ~10 km'dir.
  - **fuel_dryness** mevsime bağlıdır. Backtest bahar, güncel harita sonbahar kompozitini kullanır; iki kompozit arasında ρ = 0,51. Koridoru tümüyle su maskesine düşen bir segmentte (187664557_0019) değer NaN'dır; bu segment en düşük kuruluk riskini alır (ADR-010).
  - **strike_trees:** Kümelerin %34'ü 4 m'den alçak (F3-1 O8). Yalnız ≥4 m kümelerle yapılan varyant geriye dönük testte farklı sonuç vermedi; tanım değişmedi.
  - **fire_history** zayıf bir önseldir; tarım yakmaları gürültü katar.

## 5. Kademeler göreli
- Kademe, riskin AOI içi yüzdeliğidir: **kritik** ≥ 0,95, **yüksek** ≥ 0,80, **orta** ≥ 0,50, altı **düşük**.
- Bu yüzden her haritada kabaca aynı paylar çıkar: 46 / 139 / 278 / 462 segment. "Kritik", "ilçedeki en yüksek %5" demektir; mutlak bir tehlike düzeyi değildir.
- Farklı ilçelerin ya da tarihlerin kademeleri mutlak olarak karşılaştırılamaz. Bir segmentin kademesi, başka segmentler değişince de değişebilir.

| as_of | kritik | yüksek | orta | düşük | Skor min / medyan / max | İş paketi |
|---|---|---|---|---|---|---|
| 2025-05-31 | 46 (4,6 km) | 139 (13,9 km) | 278 (27,7 km) | 462 (46,3 km) | 16,5 / 48,8 / 78,9 | 72 (18,5 km) |
| 2026-10-30 | 46 (4,6 km) | 139 (13,8 km) | 278 (27,8 km) | 462 (46,2 km) | 19,3 / 49,0 / 77,6 | 76 (18,4 km) |

**Duyarlılık (F3-1, F3-2):**
- Tek bir ağırlığın ±%20 değişmesi sıralamayı neredeyse değiştirmiyor: Spearman ≥ 0,995, kritik küme örtüşmesi ≥ 0,913.
- Doğrusal birleştirme daha büyük bir etki yaratıyor: kritik örtüşmesi 0,80–0,85.
- Açıklık bantlarının ±%20 değişmesi vegetation_encroachment sıralamasında ρ ≥ 0,990 veriyor.
- İki as_of arasında sıralama tutarlılığı ρ = 0,953; kritik örtüşmesi 0,696, üst-%20 örtüşmesi 0,859 (yeniden üretilen haritalarda yeniden hesaplandı). Fark çoğunlukla kuruluk mevsiminden ve 2025 yangın geçmişinden geliyor (F3-2).

## 6. Önleyici kesinti senaryosu (vekil)
- **Gün ve parametreler:** 2025-06-29 (ADR-012), hamle eşiği 50 km/s, `min_tier` = yüksek. Risk haritası 2025-05-31.
- **İlçe geneli:** 92,4 km, 3469 bina (≤300 m).
- **Hedefli kesinti:** 83,4 km (%90), 3032 bina (%87), risk payı 0,917; 17 hattın 10'u.
- **Neden hedefli kesinti neredeyse ilçe geneline eşit:** Kesinti birimi OSM way'dir ve way'ler uzun iletim hatlarıdır (en uzunu 16,5 km). Birimi yalnız aday segment alan duyarlılık varyantı 18,5 km, 993 bina ve 0,260 risk payı verir. Bu bir alt sınırdır; şebeke topolojisi bilinmeden iddia edilmez.
- **Vekiller:** Gerçek kesinti birimi EDAŞ fideri ve anahtarlanabilir bölümüdür. Bina sayısı, müşteri sayısının vekilidir. Ayrıntı: docs/reports/F3-4-senaryo.md.

## 7. Geriye dönük test (as_of 2025-05-31 → 2025-06-01…09-30)
Protokol: ADR-013 ve FIX-F3 ek notu. Ayrıntı: docs/reports/F3-3-backtest.md.

- **Kayıt durumu (REV-F3F4 D2):** "Sonuç görülmeden kayıt" depodan doğrulanamaz.
  - 500 m birincil eşik, ilk iskelet commit'inden (c423a81) beri config'te sabittir.
  - FIRMS `type` filtresi 2025 sezonunda 0 tespit dışladı; pratik etkisi yok.
  - ADR-013 protokolü (`backtest` config bloğu, `type` filtresi, kod) sonuçla aynı commit'te (abe3ebb) kaydedildi.
  - İleride protokol, sonuçtan önce ayrı bir commit veya etiketle kaydedilecek.
- **Olaylar:** 788 VIIRS tespiti, 36 uzay-zaman kümesi (≤1 km, ≤2 gün). Tutuşma vekili ilçe içinde olan **10** olay var. Bunlardan **2**'si hatta ≤500 m (birincil eşik).
- **Sonuç:** Hat yakını 2 olayın hiçbiri üst %10 veya üst %20'de değil.
  - Lift 0. k = 0 olduğu için bootstrap aralığı dejeneredir (tüm yeniden örneklemler aynı payı verir). backtest.json'da `ci95: null` ve `ci95_note: "degenerate"` yazılır; belirsizliği kesin binom aralığı gösterir.
  - Kesin binom lift aralığı üst %10 için [0; 8,37], üst %20 için [0; 4,21].
  - **Test bilgi vermiyor:** Model ne doğrulandı ne çürütüldü. backtest.json'da `verdict.informative = false`.
- **Karar eşiği (`MIN_EVENTS_INFORMATIVE` = 38):** Test, ancak en az 38 hat yakını olayla bilgi verir sayılır. Gerekçe: n ≥ 38'den itibaren tek yönlü kesin binom testi (α = 0,05) üst %20 kümesinde lift 2'yi (pay 0,40'a karşı 0,20) en az %80 güçle saptar. Eşik 2025 sonucundan bağımsız bir güç hesabıdır; n = 2 olduğu için makul her eşikte karar aynıdır.
- **Taban çizgileri:** rastgele, uzunluğa orantılı, yalnız CHM, yalnız ağaç/çalı örtüsü, yalnız bina yakınlığı, yalnız geçmiş yangın, doğrusal birleştirme.
  - Model hiçbirini geçmiyor.
  - Yalnız bina yakınlığı 2 olaydan 1'ini üst %10'a, 2'sini üst %20'ye koyuyor. n = 2 ve 14 karşılaştırma içinde bu fark gürültüden ayrılamaz.
  - Bu taban çizgisi as_of'tan sonraki bina katmanına (Overture 2026-10-21.0) dayanır; sonucu iyimser olabilir (§2, statik katman beyanı).
- **Seçim yanlılığı (REV-F3F4 O4):** Pilot ilçe ve senaryo günleri (27–30 Haziran 2025) 29.06.2025 yangını ve 2024–25 yangınları yüzünden seçildi (ADR-006, ADR-012). Backtest de aynı 2025 sezonunu kullanıyor; yani test bölgesi sonuç bilinerek seçildi. Bugünkü sonuç nötr olduğu için sayılar etkilenmiyor, ama olumlu bir sonuç iyimser olurdu. Çok yıllı testte 2025 ayrı raporlanacak.
- **Duyarlılık (birincil değil):** 1000 m'de n = 2, 2000 m'de n = 5; model yine 0. Yalnız ≥4 m kümelerle yapılan strike_tall varyantı da 0.
- **Vaka: 29.06.2025 Menderes yangını.** Hat kaynaklı olduğu yalnız basında bildirildi; resmî tespit yok (F1-3 I-1).
  - FIRMS kümesinde 441 tespit var. Tutuşma vekili en yakın OSM hattına 2611 m uzakta ve ilçe sınırının 263 m dışında.
  - Bu yangın OSM hatlarıyla ilişkilendirilemiyor. Basında geçen kısa devre, haritada olmayan bir dağıtım hattını düşündürüyor.
- **İyileştirme seçenekleri:**
  - EDAŞ dağıtım hattı verisi,
  - 2016–2024 için çok yıllı kayan backtest,
  - daha geniş AOI,
  - neden ve başlangıç noktası içeren resmî yangın kayıtları.

  Her biri yeni bir protokol kaydı gerektirir.

## 8. Sınırlılıklar
- **FIRMS:** Piksel ~375 m'dir. Tespit tutuşma noktası değildir; ilk uydu geçişi tutuşmadan saatler sonra olabilir.
- **Olay tanımı:** Nedeni bilinmeyen yangınlar da olaylara dahildir; çoğu hat kaynaklı değildir. Tarım ve anız yakmaları gürültü katar.
- **Hat verisi:** OSM hatlarının çoğu iletim hattıdır. Hat kaynaklı yangınların çıkabileceği dağıtım hatları haritada yoktur.
- **Statik katmanlar:** Bina (Overture 2026-10) ve hat/ilçe sınırı (OSM 2026-10) güncel anlık görüntüdür. Backtest haritası (2025-05-31) bunları da kullanır; as_of'taki durumu göstermezler (§2). Bina yakınlığı taban çizgisi iyimser olabilir.
- **Seçim yanlılığı:** Pilot ilçe ve senaryo günleri 2025 yangını yüzünden seçildi; backtest aynı sezonu kullanıyor (§7). Olumlu bir backtest sonucu bu yüzden iyimser okunmalıdır.
- **CHM:** Görüntüler as_of'tan 5–10 yıl eskidir (§3). Hata ~2,8 m (v1).
- **Rüzgâr:** Open-Meteo ızgarası ~10 km'dir; segmentler yalnız 10 hücre kullanır. Vadi ve sırt ölçeğindeki fark, rüzgâr ölçümüyle değil yalnız TPI ile girer.
- **Kuruluk:** Backtest ve güncel harita farklı mevsim kompozitlerini kullanır. Geriye dönük testte sınanan "kuruluk", güncel haritadakiyle aynı mevsim değildir.
- **Tesis durumu:** Direk yaşı ve iletken tipi yok (asset_condition ağırlığı 0).
- **Kalibrasyon:** Ağırlıklar uzman varsayımıdır. Skor olasılık değildir. Kademeler görelidir (§5).
- **Bina vekili:** Bina sayısı müşteri sayısı değildir. İletim hattı kesintisinin etkilediği müşteriler hattın 300 m çevresiyle sınırlı değildir.
- **Tek ilçe:** Sonuçlar Menderes'e özgüdür; başka ilçeye taşınmadan önce yeniden test edilmelidir.

## 9. Yönetmelik mesafeleri: DOĞRULANMADI
- **Config bantları:** config'teki açıklık bandı genişlikleri (`clearance_band_m`: AG 1,0 m, OG 3,0 m, YG 5,0 m) **yönetmelik değeri değildir, model varsayımıdır**. Config'te `placeholder_unverified: true` işaretlidir.
- **F1-4 aktarımı:** Elektrik Kuvvetli Akım Tesisleri Yönetmeliği'nin (RG 30.11.2000, 24246) ağaçlara yatay uzaklık çizelgesi (Çizelge-7) ikincil kopyalardan aktarıldı.
  - Resmî metin mevzuat.gov.tr'den alınamadı.
  - Aktarılan değerler 1 / 2,5 / 3,0 / 4,5 m'dir; bunlar da **DOĞRULANMADI** (docs/REGULATION_NOTES.md).
- **Kullanım sonucu:** Model çıktısı bir yönetmeliğe uygunluk veya ihlal tespiti değildir; arayüzde ve sunumda "ihlal" dili kullanılmaz.
- **Doğrulama sonrası:** Bir elektrik mühendisi resmî metni doğrulayınca bantlar güncellenir ve bayrak kaldırılır. Bant ±%20 değişirse vegetation_encroachment sıralaması ρ ≥ 0,990 ile korunur (F3-1).

## 10. Tekrarlanabilirlik ve maliyet
- **Çalıştırma:** `uv run python scripts/run_pipeline.py --aoi izmir_menderes --stage <features|score|scenario|backtest|all>`
- **Tekrarlanabilirlik:** Aynı girdi aynı çıktıyı verir. Scenario ve backtest dosyalarının sha256 değerleri iki çalıştırmada aynıdır. GeoPackage dosyası yazma zaman damgası taşır, bu yüzden bayt düzeyinde aynı değildir.
- **Süre ve bellek (önbellekteki ingest verisiyle):**

  | Aşama | Süre | En yüksek bellek |
  |---|---|---|
  | features | 13,5 s | 299 MB |
  | score | 2,8 s | 190 MB |
  | scenario | 2,4 s | — |
  | backtest | 3,1 s | — |

  Bütçe 30 dk ve 4 GB'dir.
- **`compute_scenario`:** soğuk çağrı 374 ms, sıcak çağrı ortalama 3,5 ms.
