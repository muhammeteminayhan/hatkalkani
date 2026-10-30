# Durum panosu

Orkestratör günceller. Oturum başında ve bağlam sıkıştırıldıktan sonra ilk okunacak dosya budur.

**Son güncelleme:** 2026-10-30 — F0 bitti ve commit'lendi. F1 sürüyor (F1-1, F1-1b); F1B taslağı hazır.

## Fazlar
| Faz | Durum | Not |
|---|---|---|
| F0 Kurulum denetimi | ✅ | Tüm F0 görevleri bitti. Test F0-2'de koştu (1 passed). F0'da kod değişikliği olmadığı için code-reviewer ve ayrı qa turu atlandı. İlk commit kullanıcı onayıyla anahtarsız yeniden yazıldı (c423a81); kapanış commit'i atıldı |
| F1 Veri keşfi + pilot seçimi | 🔄 | F1-2 ✅ · F1-3 ✅ · F1-4 ✅ · F1-1 ve F1-1b (WorldCover örtü payı + CHM eşlemesi, data-engineer) çalışıyor · K1: pilot ilçe |
| F1B Başvuru taslağı | 🔄 | F1B-1 ✅ taslak · F1B-2 ✅ kaynak düzeltmeleri · F1B-3 ✅ taslak düzeltmesi · son geçiş 1–2 Kas (pilot ilçe, ekip, form alanları) · başvuru son tarihi 2 Kas 23:59 |
| F2 Veri hattı | ⬜ | |
| F3 Risk modeli | ⬜ | K2: sonuçlar |
| F4 API + arayüz | ⬜ | K3: demo provası |
| F5 Demo cilası + sunum | ⬜ | |
| F6 Final | ⬜ | 15–16 Kas |

Durum simgeleri: ⬜ başlamadı · 🔄 sürüyor · ✅ bitti · ⛔ engelli

## Aktif görevler
| ID | Ajan | Durum | Sahip olduğu dosyalar | Rapor |
|---|---|---|---|---|
| F1-1 | data-scout | 🔄 | data/interim/f1_overpass/ | docs/reports/F1-1-aday-ilceler.md |
| F1-1b | data-engineer | 🔄 | notebooks/f1_candidate_stats.py, data/interim/f1_candidates/ (+ F1-2'den devralınan CHM karo–ilçe eşlemesi) | docs/reports/F1-1b-ortu.md |
| — | orkestratör | sürekli | docs/STATUS.md, MANUAL_TASKS.md, docs/DECISIONS.md, docs/PLAN.md, .env.example | — |

## Biten görevler
| ID | Ajan | Sonuç | Rapor |
|---|---|---|---|
| F0-1 | orkestratör | 10 ajan + 6 skill frontmatter'ı geçerli, düzeltme gerekmedi. Kök neden yanlış klasördü: kullanıcı iç içe yapıyı düzleştirdi, proje kökü `Desktop\hatkalkani`; boş iç klasör silindi. `durum` yalnız `/durum` ile çalışır (bilinçli) | — |
| F0-2 | data-engineer (Sonnet 5.5) | git init + ilk commit (amend sonrası c423a81); uv 0.13.6 kuruldu; `uv sync` tamam; importlar tamam; `uv run pytest -q` → 1 passed; context7 yanıt verdi | docs/reports/F0-2-kurulum.md |
| F0-3 | qa-tester (Haiku 5.5) | Playwright MCP bağlandı (`mcp__playwright__*` deseni ve Windows'ta `npx` çalışıyor); ekran görüntüsü 28.997 bayt; file:// engelli, data: URL kullanıldı | docs/reports/F0-3-playwright.md |
| F0-4 | data-scout (Haiku 5.5) | Windows 11 Pro, 111 GB boş, node 24.13.0, git 2.51.1, Python 3.13.12 (sistem); `.env` var, FIRMS_MAP_KEY dolu | docs/reports/F0-4-ortam.md |
| F1B-1 | pitch-writer (Sonnet 5.5) | docs/BASVURU_TASLAK.md (10 bölüm, özet 140 kelime, elle sayıldı), docs/pitch/EKIP.md şablonu, PITCH_FACTS #21–#23. CO2e katsayısı ve resmî form alanları eksik | handoff |
| F1-3 | data-scout (Haiku 5.5) | 2025 Menderes (29.06), Çeşme (02.07) ve Ödemiş (02.07) yangınlarının hat kaynaklı olduğu yalnızca medya ve valilik aktarımında var; resmî ya da yargısal tespit yok (savcılık 15.08.2026: soruşturmaya yer yok). 2024–25 büyük yangın: Menderes 2, Çeşme 1, Ödemiş 1. PITCH #20 desteklenmiyor; #2–#4 OGM oranlarıyla çelişiyor → F1B-2'ye iletildi | docs/reports/F1-3-vakalar.md |
| F1-2 | data-scout (Haiku 5.5) | 6/7 kaynağa erişildi: CHM v1 (İzmir'de 30 karo) ve v2 (113 alt karo), Sentinel-2 `c1-l2a` (Nis–May 2025 İzmir: 407 sahne), Copernicus DEM, WorldCover (N36E024/E027, N39E024/E027), Overture 2026-10-21.0, Open-Meteo (km/h). FIRMS belirsiz: `.env` erişimi izin kuralıyla engellendi (beklenen). İlçe bazında CHM tarihleri Overpass 502 yüzünden çıkarılamadı → F1-1b'ye devredildi. 20 MB sınırı bir kez aşıldı, dosyalar silindi | docs/reports/F1-2-erisim.md |
| F1-4 | data-scout (Haiku 5.5) | mevzuat.gov.tr 404 verdi; Madde 44 ile Çizelge-7 (yatay) ve Çizelge-8 (düşey) ağaç mesafeleri, birbiriyle eşleşen iki ikincil kopyadan (isguvenligi PDF, Lexpera) REGULATION_NOTES "Ham bulgular"a aktarıldı (DOĞRULANMADI). EPDK 2026–2030 budama yükümlülüğü haberlerde doğrulandı; kurul kararı künyesi bulunamadı | docs/reports/F1-4-yonetmelik-mesafeler.md |
| F1B-2 | data-scout (Haiku 5.5) | #1 haber kaynağıyla tutarlı (birincil OGM yayını yok). #2 düzeltildi: %7 hat payı değil, "kaza" kategorisi (#24); 2021 sayı payı %3,2 (#25). #22 geçersiz. #3 doğrulanamadı. #4, #6 ve #20'ye düzeltme notu eklendi. #23: CO2e katsayısı bulunamadı. Gömülü talimat içeren bir web sayfası yok sayıldı. Rapor dosyası yazılmadı; bulgular burada | handoff |
| F1B-3 | pitch-writer (Sonnet 5.5) | Taslak düzeltildi: "%7", #22 ve #3 değerleri çıkarıldı; etki hesabı #1, #4 ve #25 ile yeniden kuruldu; vaka dili "iddia edildi / bildirildi" oldu; #23 [KAYNAK GEREKİYOR]. Özet 145 kelime (elle sayıldı; son geçişte araçla doğrulanacak) | handoff |

## Engeller
- yok (30 Eki: `.env.example`'daki gerçek biçimli FIRMS anahtarı şablondan silindi; ilk commit kullanıcı onayıyla `--amend` ile yeniden yazıldı: 87d9e3b → c423a81)

## İzlenecekler
- GateGuard alt ajanları aksatmadı (F0-3, F0-4, F1B-1); kanca notu görev metinlerinde kalıyor.
- Playwright MCP file:// adreslerini engelliyor; arayüz testleri `scripts/serve.py` üzerinden http://localhost ile yapılacak.
- pitch-writer'da Bash yok; kelime sayıları elle yapıldı. 2 Kas son geçişinde başka bir ajanla doğrulanacak.
- Satır sonu uyarıları (LF→CRLF); `.gitattributes` eklenmesi düşük öncelikli.
- FIRMS anahtarının geçerliliği F2-5'te, değeri göstermeyen betikle sınanacak; ajan komutlarının `.env`'e erişimi izin kuralıyla engelli ve bu beklenen bir durum.
- geo-data-sources skill'i için F1-2'nin önerdiği güncellemeler (v2 için tiles.geojson yerine chm/ listeleme, tarih için metadata acq_date) F1 sonunda uygulanacak.
- Sunum dili: 2025 İzmir yangınlarının hat kaynaklı olduğu resmî olarak tespit edilmedi (F1-3). Başvuru ve sunumda "bildirildi / iddia edildi" dili kullanılmalı; 1–2 Kas son geçişinde pitch-writer'a verilecek.

## Kullanıcıdan beklenenler
MANUAL_TASKS.md'ye bak: 10, 10a ve 10b (1 Kas), 12 (3 Kas), K1.

## Önemli sonuçlar (sayılar, kaynak dosyasıyla)
- Ortam: uv 0.13.6, Python 3.12.16 (venv), geopandas 1.2.0, rasterio 1.5.2, pystac-client 0.9.1, odc-stac 0.5.3, duckdb 2.0.0, fastapi 0.162.0 — docs/reports/F0-2-kurulum.md
- Başvuru taslağı etki aralığı (F1B-3): kaçınılan alan = 81.473 ha × hat payı (%20 / %22,5 / %25; #4, #25) × kapsama (%10 / %30 / %50) × kaçınma (%1 / %3 / %5) ≈ 16 / 165 / 509 ha/yıl, yani toplam yanan alanın ≈ %0,02 / %0,2 / %0,6. Kapsama ve kaçınma [VARSAYIM]; #4 ve #25 uzman hesabı; CO2e yok (#23) — docs/BASVURU_TASLAK.md
- Hat kaynaklı yangın payı: "%7" hat payı değil, "kaza" kategorisi (#24); 2021'de sayıca pay %3,2 (#25); #22 geçersiz — docs/PITCH_FACTS.md

## Model yükseltmeleri
Hangi görev neden Opus'a yükseltildi:
- yok
