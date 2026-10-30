# Durum panosu

Orkestratör günceller. Oturum başında ve bağlam sıkıştırıldıktan sonra ilk okunacak dosya budur.

**Son güncelleme:** 2026-10-30 — K1 tamam: pilot Menderes (ADR-006), hat verisi OSM + EDAŞ dosyası (ADR-007). F1 kapandı ve commit'lendi; F2-1 çalışıyor.

## Fazlar
| Faz | Durum | Not |
|---|---|---|
| F0 Kurulum denetimi | ✅ | Tüm F0 görevleri bitti. Test F0-2'de koştu (1 passed). F0'da kod değişikliği olmadığı için code-reviewer ve ayrı qa turu atlandı. İlk commit kullanıcı onayıyla anahtarsız yeniden yazıldı (c423a81); kapanış commit'i atıldı |
| F1 Veri keşfi + pilot seçimi | ✅ | K1 ✅ Menderes (ADR-006, ADR-007) · QA-F1 ✅ (duman testi, ruff, önbellekten aynı CSV'ler) · F1 commit'i atıldı · code-reviewer F1'de atlandı: yalnızca keşif betiği var, tam inceleme F2 sonunda |
| F1B Başvuru taslağı | 🔄 | F1B-1 ✅ taslak · F1B-2 ✅ kaynak düzeltmeleri · F1B-3 ✅ taslak düzeltmesi · son geçiş 1–2 Kas (pilot ilçe, ekip, form alanları) · başvuru son tarihi 2 Kas 23:59 |
| F2 Veri hattı | 🔄 | F2-1 (sınır, hatlar, 100 m segment, EDAŞ girişi) çalışıyor |
| F3 Risk modeli | ⬜ | K2: sonuçlar |
| F4 API + arayüz | ⬜ | K3: demo provası |
| F5 Demo cilası + sunum | ⬜ | |
| F6 Final | ⬜ | 15–16 Kas |

Durum simgeleri: ⬜ başlamadı · 🔄 sürüyor · ✅ bitti · ⛔ engelli

## Aktif görevler
| ID | Ajan | Durum | Sahip olduğu dosyalar | Rapor |
|---|---|---|---|---|
| F2-1 | data-engineer | 🔄 | src/hatkalkani/ingest/ (yeni modüller), tests/ingest/, data/raw/izmir_menderes/, data/raw/MANIFEST.csv, data/processed/izmir_menderes/ | handoff |
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
- FIRMS anahtarının geçerliliği F2-5'te, değeri göstermeyen betikle sınanacak; ajan komutlarının `.env`'e erişimi izin kuralıyla engelli ve bu beklenen bir durum.
- F1 kapanışında DATA_SOURCES.md ve ATTRIBUTIONS.md'ye WorldCover 2021 ve OSM (ODbL) satırları eklenecek (F1-1b önerisi).
- geo-data-sources skill'i için F1-2'nin önerdiği güncellemeler (v2 için tiles.geojson yerine chm/ listeleme, tarih için metadata acq_date) F1 sonunda uygulanacak.
- Sunum dili: 2025 İzmir yangınlarının hat kaynaklı olduğu resmî olarak tespit edilmedi (F1-3). Başvuru ve sunumda "bildirildi / iddia edildi" dili kullanılmalı; 1–2 Kas son geçişinde pitch-writer'a verilecek.

## Kullanıcıdan beklenenler
MANUAL_TASKS.md'ye bak: 10, 10a ve 10b (1 Kas), 12 (3 Kas), 15 (GDZ hat verisi talebi).

## Önemli sonuçlar (sayılar, kaynak dosyasıyla)
- Ortam: uv 0.13.6, Python 3.12.16 (venv), geopandas 1.2.0, rasterio 1.5.2, pystac-client 0.9.1, odc-stac 0.5.3, duckdb 2.0.0, fastapi 0.162.0 — docs/reports/F0-2-kurulum.md
- Başvuru taslağı etki aralığı (F1B-3): kaçınılan alan = 81.473 ha × hat payı (%20 / %22,5 / %25; #4, #25) × kapsama (%10 / %30 / %50) × kaçınma (%1 / %3 / %5) ≈ 16 / 165 / 509 ha/yıl, yani toplam yanan alanın ≈ %0,02 / %0,2 / %0,6. Kapsama ve kaçınma [VARSAYIM]; #4 ve #25 uzman hesabı; CO2e yok (#23) — docs/BASVURU_TASLAK.md
- K1 adayları (kırpılmış hat km / ±30 m koridor ağaç+çalı %): Menderes 92 / 52,6 · Çeşme 98 / 24,8 · Ödemiş 106 / 24,3 · Seferihisar 43 / 82,7 · Torbalı 161 / 47,2. 33–36 kV etiketli hat yalnız Torbalı'da var (4 km); ≥154 kV: Menderes 61, Torbalı 117 km — docs/reports/F1-1b-ortu.md
- Hat kaynaklı yangın payı: "%7" hat payı değil, "kaza" kategorisi (#24); 2021'de sayıca pay %3,2 (#25); #22 geçersiz — docs/PITCH_FACTS.md

## Model yükseltmeleri
Hangi görev neden Opus'a yükseltildi:
- yok
