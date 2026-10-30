# Durum panosu

Orkestratör günceller. Oturum başında ve bağlam sıkıştırıldıktan sonra ilk okunacak dosya budur.

**Son güncelleme:** 2026-10-31 — F2 bitti ve commit'lendi: tek komutla ingest önbellekten ~25 sn, testler geçiyor, Yüksek bulgular düzeltildi. Sıradakiler: F3 (kullanıcı onayıyla) ve başvuru son geçişi (1–2 Kas).

## Fazlar
| Faz | Durum | Not |
|---|---|---|
| F0 Kurulum denetimi | ✅ | Tüm F0 görevleri bitti. Test F0-2'de koştu (1 passed). F0'da kod değişikliği olmadığı için code-reviewer ve ayrı qa turu atlandı. İlk commit kullanıcı onayıyla anahtarsız yeniden yazıldı (c423a81); kapanış commit'i atıldı |
| F1 Veri keşfi + pilot seçimi | ✅ | K1 ✅ Menderes (ADR-006, ADR-007) · QA-F1 ✅ (duman testi, ruff, önbellekten aynı CSV'ler) · F1 commit'i atıldı · code-reviewer F1'de atlandı: yalnızca keşif betiği var, tam inceleme F2 sonunda |
| F1B Başvuru taslağı | 🔄 | F1B-1 ✅ taslak · F1B-2 ✅ kaynak düzeltmeleri · F1B-3 ✅ taslak düzeltmesi · son geçiş 1–2 Kas (pilot ilçe, ekip, form alanları) · başvuru son tarihi 2 Kas 23:59 |
| F2 Veri hattı | ✅ | F2-1…F2-6, DOC-F2 ✅ · QA-F2 ✅ · REV-F2: Kritik 0, Yüksek 3 → FIX-F2 ✅ · commit'lendi · açık: ATTR-1 (web limiti), backlog'da 10 Orta ve 15 Düşük bulgu |
| F3 Risk modeli | ⬜ | K2: sonuçlar |
| F4 API + arayüz | ⬜ | K3: demo provası |
| F5 Demo cilası + sunum | ⬜ | |
| F6 Final | ⬜ | 15–16 Kas |

Durum simgeleri: ⬜ başlamadı · 🔄 sürüyor · ✅ bitti · ⛔ engelli

## Aktif görevler
| ID | Ajan | Durum | Sahip olduğu dosyalar | Rapor |
|---|---|---|---|---|
| — | orkestratör | sürekli | docs/STATUS.md, MANUAL_TASKS.md, docs/DECISIONS.md, docs/PLAN.md, config/aoi.yaml, .env.example | — |

## Biten görevler
| ID | Ajan | Sonuç | Rapor |
|---|---|---|---|
| F0-1 | orkestratör | 10 ajan + 6 skill frontmatter'ı geçerli, düzeltme gerekmedi. Kök neden yanlış klasördü: kullanıcı iç içe yapıyı düzleştirdi, proje kökü `Desktop\hatkalkani`; boş iç klasör silindi. `durum` yalnız `/durum` ile çalışır (bilinçli) | — |
| F0-2 | data-engineer (Sonnet 5.5) | git init + ilk commit (amend sonrası c423a81); uv 0.13.6 kuruldu; `uv sync` tamam; importlar tamam; `uv run pytest -q` → 1 passed; context7 yanıt verdi | docs/reports/F0-2-kurulum.md |
| F0-3 | qa-tester (Haiku 5.5) | Playwright MCP bağlandı (`mcp__playwright__*` deseni ve Windows'ta `npx` çalışıyor); ekran görüntüsü 28.997 bayt; file:// engelli, data: URL kullanıldı | docs/reports/F0-3-playwright.md |
| F0-4 | data-scout (Haiku 5.5) | Windows 11 Pro, 111 GB boş, node 24.13.0, git 2.51.1, Python 3.13.12 (sistem); `.env` var, FIRMS_MAP_KEY dolu | docs/reports/F0-4-ortam.md |
| F1B-1 | pitch-writer (Sonnet 5.5) | docs/BASVURU_TASLAK.md (10 bölüm, özet 140 kelime, elle sayıldı), docs/pitch/EKIP.md şablonu, PITCH_FACTS #21–#23. CO2e katsayısı ve resmî form alanları eksik | handoff |
| F1-3 | data-scout (Haiku 5.5) | 2025 Menderes (29.06), Çeşme (02.07) ve Ödemiş (02.07) yangınlarının hat kaynaklı olduğu yalnızca medya ve valilik aktarımında var; resmî ya da yargısal tespit yok (savcılık 15.08.2026: soruşturmaya yer yok). 2024–25 büyük yangın: Menderes 2, Çeşme 1, Ödemiş 1. PITCH #20 desteklenmiyor; #2–#4 OGM oranlarıyla çelişiyor → F1B-2'ye iletildi | docs/reports/F1-3-vakalar.md |
| F1-1 | data-scout (Haiku 5.5) | 5 aday ölçüldü: Menderes, Çeşme, Ödemiş ve ek olarak Seferihisar, Torbalı. power=line km: 204 / 179 / 143 / 84 / 324. Bunlar üst sınır, çünkü length() sınırı aşan hattın tamamını sayıyor. minor_line yalnız 0–1,7 km (Torbalı 16); direk 0–31. OSM'ye göre öneri: Menderes, sonra Çeşme. Yüzölçümü Vikipedi'den | docs/reports/F1-1-aday-ilceler.md |
| FIX-F2 | data-engineer (Sonnet 5.5) | Y1: CHM raster ve istatistik önbelleği ayrıldı; `stats_cache_key` tüm parametreleri içeriyor. Y2: FIRMS yolu `data/raw/firms/<aoi>/<kaynak>_<yıl>.csv` ve `.meta.json` eki; 33 dosya indirilmeden taşındı. Y3: lisans kayıt bazında ham veriden okunuyor (ODbL-1.0); ATTRIBUTIONS düzeltildi. Her biri için regresyon testi var. ruff temiz, pytest geçti; ingest 25 sn, indirme yok; 4 parquet'in sha256'sı değişmedi | handoff |
| REV-F2 | code-reviewer (Opus 5.5) | Kritik yok, Yüksek 3: Y1 CHM önbellek anahtarında bant ve strike parametreleri yok; Y2 FIRMS yıl dosyaları AOI'ye ve döneme bağlı değil; Y3 Overture bina lisansı yanlış (CDLA değil, ODbL-1.0) → FIX-F2. Orta 10, Düşük 15 → backlog. Geçenler: FIRMS anahtarı maskeli (33/33), CRS, birimler, segmentasyon, bellek. Kısmi: CHM uint8 metre varsayımı çalışma anında doğrulanmıyor; FIRMS ve rüzgârda dönem etiketi yok; CHM v2'de tarih olmadığı doğrulanmadı (metadata/ incelenmedi) | docs/reports/review-F2.md |
| QA-F2 | qa-tester (Haiku 5.5) | ruff temiz; pytest 48 geçti, 2 ağ testi seçilmedi; pipeline önbellekten çıkış kodu 0, MANIFEST OK, modüllerin toplamı 28,5 sn; 5 dosyanın sha256'sı çalıştırmadan önce ve sonra aynı (idempotent). Düşük: addopts'ta yinelenen `-q` (özet satırı basılmıyor); chm.py:423'te shapely DeprecationWarning | docs/reports/qa-F2.md |
| F2-6 | data-engineer (Sonnet 5.5) | scripts/run_pipeline.py (boundary → … → weather; `--only`, `--force`; aşama süreleri; sonda MANIFEST doğrulaması); sentinel2 `periods.current_asof` kullanıyor; tests/test_pipeline.py 6 test. ruff temiz, pytest 48 geçti; tüm ingest önbellekten 29,2 sn, "MANIFEST validation OK" | data/interim/logs/f2_6_run.log |
| ATTR-1 | data-scout (Haiku 5.5) | ❌ Doğrulanamadı: WebFetch ve WebSearch aylık harcama limitine takıldı (sıfırlanma 23:40, İstanbul); Copernicus ECONNREFUSED, AWS kayıt sayfası 404. ATTRIBUTIONS.md değişmedi. Limit sıfırlanınca yeniden denenecek | docs/reports/ATTR-1-atif-dogrulama.md |
| DOC-F2 | doc-writer (Haiku 5.5) | ATTRIBUTIONS.md'de 8 kaynak tamamlandı, yer tutucular kaldırıldı; DATA_SOURCES.md'ye sürüm ve erişim tarihi tablosu eklendi; geo-data-sources skill'inde 3 düzeltme (FIRMS 5 gün, CHM v2 chm/ listesi, v1 acq_date). DEM ve CHM v2 atıf metinleri [DOĞRULANMADI] → ATTR-1 | handoff |
| F2-5 | data-engineer (Sonnet 5.5) | firms.py: bbox + 5 km; VIIRS SNPP, NOAA-20 ve MODIS (SP ve NRT kuyruğu); anahtar maskeli; API tek istekte en fazla 5 gün alıyor (skill'deki 10 yanlış). weather.py: 16 noktalı ~10 km ızgara, 2022–24 Haz–Eyl ve 27–30 Haz 2025, m/s. FIRMS anahtarı geçerli. 10 test geçti; önbellekten firms 20 sn, weather 4 sn; ilk FIRMS indirmesi ~25 dk | handoff |
| F2-2 | data-engineer (Sonnet 5.5) | sentinel2.py, dem.py, worldcover.py ve ortak rasters.py. S2 `c1-l2a` 20 m, SCL maskesi, sahne başına indeks ve ardından zaman medyanı: backtest 24 sahne (13 gün), güncel pencere 21 sahne (12 gün). DEM GLO-30 (eğim, TPI yarıçapı 300 m); WorldCover v200 doğrudan S3'ten. Tüm çıktılar EPSG:32635 COG. 7 test geçti; önbellekten 14 sn. Not: ingest/ altında başka bir dosyada 1 ruff hatası var | handoff |
| F2-3 | data-engineer (Sonnet 5.5) | chm.py: CHM v2 (dinov3_global_chm_v2_ml3) seçildi (ADR-008); 4 karodan pencereli okuma (≈8 MB), 1 m'de EPSG:32635. chm_segment_stats.parquet 925 satır, NaN yok: p90'ın medyanı 2,0 m (ortalama 3,7, en yüksek 27), max'ın medyanı 7 m. v2'de görüntü tarihi yok. 8 test geçti, ruff temiz; 66 sn, önbellekten 5 sn | handoff |
| F2-4 | data-engineer (Sonnet 5.5) | buildings.py: Overture 2026-10-21.0, DuckDB ile yalnız bbox okuma (OSM yedeği yalnız birim testli). 65.873 bina (Microsoft ML Buildings %87,3, OSM %12,7); hatlara 300 m içinde 3.633 bina; lisans kayıt bazında ODbL-1.0 (önce yanlışlıkla CDLA yazılmıştı; FIX-F2 düzeltti). 6 test geçti, ruff temiz; 87 sn, önbellekten 9 sn | handoff |
| F2-1 | data-engineer (Sonnet 5.5) | ingest/{common,boundary,lines,segments}.py (modül CLI'ları, Overpass, MANIFEST, sha256 önbelleği); Menderes sınırı 787,2 km²; 17 hat, 92,4 km (≥154 kV 61,0; etiketsiz 31,5, 0,4 km minor_line dahil); 925 segment (58–142 m, medyan 100); EDAŞ girişi `--edas-dir` (varsayılan data/manual/edas/). ruff temiz, pytest 11 geçti (1 ağ testi atlandı); önbellekten ≈10 sn | handoff |
| QA-F1 | qa-tester (Haiku 5.5) | `pytest tests/test_smoke.py` geçti; ruff temiz; f1 betiği önbellekten 7 sn, iki CSV'nin sha256'sı değişmedi. Not: konsolda Türkçe karakterler bozuk görünüyor (yalnız stdout) | docs/reports/qa-F1.md |
| F1-1b | data-engineer (Sonnet 5.5) | 30 İzmir ilçesi için WorldCover 2021 ağaç+çalı payı; 5 aday için kırpılmış hat km'si, gerilim sınıfı, ±30 m koridor payı, CHM karoları (v1 tarihleri 2016–2020; Ödemiş ve Torbalı kısmi). Betik önbellekten 5 sn'de çalışıyor; ruff geçti; birim testi yok | docs/reports/F1-1b-ortu.md |
| F1-2 | data-scout (Haiku 5.5) | 6/7 kaynağa erişildi: CHM v1 (İzmir'de 30 karo) ve v2 (113 alt karo), Sentinel-2 `c1-l2a` (Nis–May 2025 İzmir: 407 sahne), Copernicus DEM, WorldCover (N36E024/E027, N39E024/E027), Overture 2026-10-21.0, Open-Meteo (km/h). FIRMS belirsiz: `.env` erişimi izin kuralıyla engellendi (beklenen). İlçe bazında CHM tarihleri Overpass 502 yüzünden çıkarılamadı → F1-1b'ye devredildi. 20 MB sınırı bir kez aşıldı, dosyalar silindi | docs/reports/F1-2-erisim.md |
| F1-4 | data-scout (Haiku 5.5) | mevzuat.gov.tr 404 verdi; Madde 44 ile Çizelge-7 (yatay) ve Çizelge-8 (düşey) ağaç mesafeleri, birbiriyle eşleşen iki ikincil kopyadan (isguvenligi PDF, Lexpera) REGULATION_NOTES "Ham bulgular"a aktarıldı (DOĞRULANMADI). EPDK 2026–2030 budama yükümlülüğü haberlerde doğrulandı; kurul kararı künyesi bulunamadı | docs/reports/F1-4-yonetmelik-mesafeler.md |
| F1B-2 | data-scout (Haiku 5.5) | #1 haber kaynağıyla tutarlı (birincil OGM yayını yok). #2 düzeltildi: %7 hat payı değil, "kaza" kategorisi (#24); 2021 sayı payı %3,2 (#25). #22 geçersiz. #3 doğrulanamadı. #4, #6 ve #20'ye düzeltme notu eklendi. #23: CO2e katsayısı bulunamadı. Gömülü talimat içeren bir web sayfası yok sayıldı. Rapor dosyası yazılmadı; bulgular burada | handoff |
| F1B-3 | pitch-writer (Sonnet 5.5) | Taslak düzeltildi: "%7", #22 ve #3 değerleri çıkarıldı; etki hesabı #1, #4 ve #25 ile yeniden kuruldu; vaka dili "iddia edildi / bildirildi" oldu; #23 [KAYNAK GEREKİYOR]. Özet 145 kelime (elle sayıldı; son geçişte araçla doğrulanacak) | handoff |

## Engeller
- yok (30 Eki: `.env.example`'daki gerçek biçimli FIRMS anahtarı şablondan silindi; ilk commit kullanıcı onayıyla `--amend` ile yeniden yazıldı: 87d9e3b → c423a81)

## İzlenecekler
- **Ana veri riski:** OSM'de orta gerilim dağıtım hatları neredeyse yok; aday ilçelerde minor_line 0–16 km, direk 0–31. Ölçülen power=line uzunluğu az sayıda uzun way'den geliyor ve büyük olasılıkla iletim hatları (gerilim dağılımı F1-1b'de). Müşteri EDAŞ olduğu için hat verisi stratejisi K1'de kullanıcıya ayrı karar olarak sunulacak (EDAŞ verisi: MANUAL 15).
- GateGuard alt ajanları aksatmadı (F0-3, F0-4, F1B-1); kanca notu görev metinlerinde kalıyor.
- Playwright MCP file:// adreslerini engelliyor; arayüz testleri `scripts/serve.py` üzerinden http://localhost ile yapılacak.
- pitch-writer'da Bash yok; kelime sayıları elle yapıldı. 2 Kas son geçişinde başka bir ajanla doğrulanacak.
- Satır sonu uyarıları (LF→CRLF); `.gitattributes` eklenmesi düşük öncelikli.
- FIRMS anahtarı F2-5'te betikle sınandı ve geçerli çıktı; değeri hiçbir yerde gösterilmedi. Ajan komutlarının `.env`'e doğrudan erişimi izin kuralıyla engelli ve bu beklenen bir durum.
- ✅ F2-6: S2 güncel penceresi artık `periods.current_asof`'a (2026-10-30) bağlı; gün değişince önbellek bozulmuyor.
- F3'e devredilecekler (REV-F2): FIRMS ve rüzgâr dosyalarında dönem etiketi yok, `as_of` ile sızıntı testi F3-1'de yazılmalı; UTC ile yerel gün sınırı tanımlanmalı. CHM v2 `metadata/` klasöründe görüntü tarihi var mı, data-scout bakmalı (S3 listesi curl ile alınabilir; web limiti bunu etkilemez). review-F2.md'deki 10 Orta ve 15 Düşük bulgu backlog'da; aralarında EDAŞ'ın Türkçe sütun adları ("GERİLİM") ve OSM yedeğine sessiz geçiş var.
- REV-F2 sonucu (F3'te dikkate alınacak): CHM'nin uint8 metre olduğu varsayımı değer dağılımıyla (0–32 m) uyumlu, ama çalışma anında doğrulanmıyor. Yaklaşım bandı genişlikleri config'te yer tutucu; chm_meta.json'da `placeholder_unverified` bayrağı var. CHM taban yılı bilinmiyor; MODEL_CARD'a yazılacak.
- ✅ DOC-F2 ve FIX-F2: ATTRIBUTIONS.md ile DATA_SOURCES.md güncel; Overture binaları ODbL-1.0 (Microsoft ML Buildings ve OSM). DEM ve CHM v2 atıf metinleri hâlâ [DOĞRULANMADI]; ATTR-1 web limiti sıfırlanınca yeniden denenecek.
- ✅ geo-data-sources skill'i DOC-F2'de düzeltildi: FIRMS 5 gün, CHM v2 için chm/ listesi, v1 için acq_date.
- Sunum dili: 2025 İzmir yangınlarının hat kaynaklı olduğu resmî olarak tespit edilmedi (F1-3). Başvuru ve sunumda "bildirildi / iddia edildi" dili kullanılmalı; 1–2 Kas son geçişinde pitch-writer'a verilecek.

## Kullanıcıdan beklenenler
MANUAL_TASKS.md'ye bak: 10, 10a ve 10b (1 Kas), 12 (3 Kas), 15 (GDZ hat verisi talebi).

## Önemli sonuçlar (sayılar, kaynak dosyasıyla)
- Ortam: uv 0.13.6, Python 3.12.16 (venv), geopandas 1.2.0, rasterio 1.5.2, pystac-client 0.9.1, odc-stac 0.5.3, duckdb 2.0.0, fastapi 0.162.0 — docs/reports/F0-2-kurulum.md
- Başvuru taslağı etki aralığı (F1B-3): kaçınılan alan = 81.473 ha × hat payı (%20 / %22,5 / %25; #4, #25) × kapsama (%10 / %30 / %50) × kaçınma (%1 / %3 / %5) ≈ 16 / 165 / 509 ha/yıl, yani toplam yanan alanın ≈ %0,02 / %0,2 / %0,6. Kapsama ve kaçınma [VARSAYIM]; #4 ve #25 uzman hesabı; CO2e yok (#23) — docs/BASVURU_TASLAK.md
- FIRMS (Menderes bbox + 5 km; VIIRS SNPP + NOAA-20 + MODIS birlikte, uydular arası yineleme var, olay sayısı değildir) yıllık tespit: 2015: 65 · 2016: 120 · 2017: 124 · 2018: 124 · 2019: 957 · 2020: 191 · 2021: 79 · 2022: 88 · 2023: 196 · 2024: 254 · 2025: 982. 29.06.2025 ±2 gün: 590 (29 Haz 436, 30 Haz 141, 1 Tem 13) — data/interim/izmir_menderes/firms.parquet
- Open-Meteo en yüksek hamle (m/s, 16 nokta): 27 Haz 15,2 · 28 Haz 19,8 · 29 Haz 24,0 · 30 Haz 19,5 (2025). F2-5 senaryo günü olarak 29 Haziran'ı öneriyor; seçim F3-4'te yapılıp DECISIONS'a yazılacak — wind_hourly.parquet
- Menderes hat ağı (OSM, 30 Eki 2026): 17 hat, 92,4 km (≥154 kV 61,0 km; etiketsiz 31,5 km), 925 segment (58–142 m, medyan 100 m) — data/processed/izmir_menderes/
- K1 adayları (kırpılmış hat km / ±30 m koridor ağaç+çalı %): Menderes 92 / 52,6 · Çeşme 98 / 24,8 · Ödemiş 106 / 24,3 · Seferihisar 43 / 82,7 · Torbalı 161 / 47,2. 33–36 kV etiketli hat yalnız Torbalı'da var (4 km); ≥154 kV: Menderes 61, Torbalı 117 km — docs/reports/F1-1b-ortu.md
- Hat kaynaklı yangın payı: "%7" hat payı değil, "kaza" kategorisi (#24); 2021'de sayıca pay %3,2 (#25); #22 geçersiz — docs/PITCH_FACTS.md

## Model yükseltmeleri
Hangi görev neden Opus'a yükseltildi:
- yok
