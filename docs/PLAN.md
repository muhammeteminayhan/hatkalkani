# İş planı

Orkestratör bu planı yürütür; ilerleme docs/STATUS.md'ye yazılır. Tarihler İstanbul saatiyle hedeftir.

- **Paralel işaretli görevler:** Arka planda birlikte çalışabilir; dosyaları ayrıdır.
- **K işaretli satırlar:** Kullanıcı onayı olmadan geçilmez.

## Takvim özeti
| Faz | Hedef tarih | Çıkış |
|---|---|---|
| F0 Kurulum denetimi | 30 Eki | Ajanlar, skill'ler ve MCP çalışıyor; `uv run pytest` geçiyor; git hazır |
| F1 Veri keşfi + pilot seçimi | 31 Eki | Veri erişim raporu, aday ilçe karşılaştırması, vaka listesi → **K1** |
| F1B Başvuru taslağı (paralel) | 1 Kas akşamı | docs/BASVURU_TASLAK.md (kullanıcı 2 Kas 23:59'a kadar gönderir) |
| F2 Veri hattı | 31 Eki – 3 Kas | Pilot ilçe için tüm ham ve ara veriler, tek komutla tekrar üretilebilir |
| F3 Risk modeli | 3 – 6 Kas | Skor, iş paketleri, geriye dönük test, senaryo, MODEL_CARD → **K2** |
| F4 API + arayüz | 5 – 10 Kas | Çalışan demo, duman testleri, ekran görüntüleri → **K3** |
| F5 Demo cilası + sunum | 9 – 14 Kas | Çevrimdışı mod, TR/EN, sunum akışı, soru-cevap, saha kiti, temiz klon provası |
| F6 Final | 15 – 16 Kas | `final-start` etiketi, en az 1 saha geri bildirimi uygulanmış, FINAL_CHANGELOG |

6 Kasım'da finalist olunamazsa F4'ten sonrası takımın kararıyla devam eder.

**31 Eki güncellemesi (kullanıcı yönü):** F3 ve F4, 1 Kas sabahına kadar çalışan prototip hedefiyle sıkıştırıldı. API ve arayüz F3-3/F3-4 ile paralel yazılıyor (ADR-011). F3-5 ve F4-4 incelemeleri tek code-reviewer turunda birleşiyor. Sunum ve başvuru işleri (F1B son geçiş, F5-3) sonraya kaldı; K2 ve K3 yine kullanıcı onayına sunulur.

---

## F0 — Kurulum denetimi
| ID | Ajan | İş | Kabul kriteri |
|---|---|---|---|
| F0-1 | orkestratör | `.claude/agents` ve `.claude/skills` yüklendi mi kontrol et; frontmatter hatası varsa düzelt | 10 ajan ve 6 skill görünür |
| F0-2 | data-engineer | uv yoksa kur; `uv sync`; import testi (geopandas, rasterio, pystac_client, odc.stac, duckdb, fastapi); `git init` + ilk commit (.env hariç); context7 ile tek bir kütüphane dokümanı sorgusu | `uv run pytest` → 1 passed; context7 yanıt verdi |
| F0-3 | qa-tester | Playwright MCP'yi dene: herhangi bir yerel HTML'i aç ve ekran görüntüsü al | `docs/screens/F0-playwright.png` var |
| F0-4 | data-scout | Ortam özeti: işletim sistemi, boş disk, Node.js sürümü, `.env` var mı, FIRMS_MAP_KEY boş mu (değeri yazdırmadan) | docs/reports/F0-4-ortam.md |

- **MCP sunucusu bağlanmazsa:** Klasör güven onayı ve Node.js varlığını kontrol et.
- **Hâlâ olmuyorsa:** Kullanıcıya iki seçenek sun: (a) context7'yi `.mcp.json`'a taşı; (b) playwright yerine Python Playwright ile test et.

## F1 — Veri keşfi ve pilot seçimi (data-scout görevleri paralel)
| ID | Ajan | İş | Çıktı |
|---|---|---|---|
| F1-1 | data-scout | Aday ilçeler (config/aoi.yaml) için OSM sayımları: havai hat km (line / minor_line ayrı), voltage etiketli oran, direk sayısı. Gerekçesiyle en fazla 2 aday daha önerebilir. | docs/reports/F1-1-aday-ilceler.md (karşılaştırma tablosu + öneri) |
| F1-2 | data-scout | geo-data-sources'taki [K] maddelerini doğrula: CHM v2/v1 İzmir karo kapsaması ve görüntü tarihleri, S2 koleksiyon adı, DEM, WorldCover dosya adı, Overture son release, Open-Meteo parametreleri, FIRMS erişimi (anahtar varsa 1 küçük istek) | docs/DATA_SOURCES.md güncel + docs/reports/F1-2-erisim.md |
| F1-3 | data-scout | Belgelenmiş hat kaynaklı yangınlar (2023–2026; önce İzmir, sonra Türkiye): tarih, ilçe, yaklaşık konum, dayanak, URL | docs/reports/F1-3-vakalar.md |
| F1-4 | data-scout | Elektrik Kuvvetli Akım Tesisleri Yönetmeliği: ağaçlara yatay/düşey mesafe tabloları ve ilgili maddeler (ham aktarım) | docs/REGULATION_NOTES.md "Ham bulgular" (DOĞRULANMADI) |
| F1B-1 | pitch-writer | Başvuru taslağı (paralel; veriye bağlı değil): problem, çözüm, yenilik, birimli iklim etkisi, iş modeli, ekip (yer tutucu), yol haritası + 150 kelimelik özet | docs/BASVURU_TASLAK.md |

**K1 — Pilot ilçe seçimi:** Orkestratör F1-1 ve F1-2'ye dayanarak 2–3 seçenek ve bir öneri sunar. Kullanıcı seçer. `config/aoi.yaml → selected` doldurulur ve DECISIONS'a ADR yazılır.

## F2 — Veri hattı (pilot ilçe)
Sıra: önce F2-1, sonra F2-2…F2-5 paralel, en son F2-6.

| ID | Ajan | İş | Çıktı | Bağımlılık |
|---|---|---|---|---|
| F2-1 | data-engineer | İlçe sınırı, OSM havai hatlar, direkler, 100 m segmentasyon (risk-model-spec §1) | data/processed/<aoi>/lines.parquet, segments.parquet | K1 |
| F2-2 | data-engineer | Sentinel-2 NDVI/NDMI kompozitleri (backtest + güncel dönem), DEM türevleri (eğim, TPI), WorldCover kırpma | data/interim/<aoi>/s2_*.tif, dem_*.tif, worldcover.tif | F2-1 (AOI) |
| F2-3 | data-engineer | CHM koridor çıkarımı (±30 m): v2 veya v1, pencereli okuma, koridor rasteri veya segment başına ham istatistik | data/interim/<aoi>/chm_corridor.tif + chm_meta.json (görüntü tarihi) | F2-1 |
| F2-4 | data-engineer | Binalar (Overture veya OSM yedeği) | data/interim/<aoi>/buildings.parquet | F2-1 |
| F2-5 | data-engineer | FIRMS 2015–2025 (AOI bbox + 5 km) ve Open-Meteo saatlik rüzgâr (klimatoloji yazları + senaryo günleri) | data/interim/<aoi>/firms.parquet, wind_hourly.parquet | F2-1, FIRMS_MAP_KEY |
| F2-6 | data-engineer | `scripts/run_pipeline.py --aoi <id> --stage ingest` tek komut; MANIFEST eksiksiz | komut önbellekle 5 dk altında biter | F2-2…F2-5 |

**Faz sonu:** qa-tester (testler) → code-reviewer (CRS, bellek, idempotentlik) → commit.

**Başvuru günü (2 Kas):** Kullanıcıya hatırlat. Mümkünse ilk segment haritasının ekran görüntüsünü al: data-engineer basit bir statik PNG, qa-tester ekran görüntüsü. Taslağı son haline getirmek için pitch-writer'ı bir kez daha çalıştır.

## F3 — Risk modeli
| ID | Ajan | İş | Çıktı |
|---|---|---|---|
| F3-1 | risk-modeler | Özellikler, `as_of` parametreli (risk-model-spec §2) + sızıntı testi | features.parquet, tests/features |
| F3-2 | risk-modeler | Skor, kademe, top_factors, iş paketleri, dışa aktarım dosyaları | risk.parquet, risk.geojson, workorders.* |
| F3-3 | risk-modeler | Geriye dönük test (lift, güven aralığı, taban çizgileri, vaka incelemeleri) | backtest.json, events_2025.geojson, docs/MODEL_CARD.md |
| F3-4 | risk-modeler | Kesinti senaryosu motoru + senaryo günü seçimi + duyarlılık tablosu | scenario_<tarih>.json, scenario_dates.json |
| F3-5 | code-reviewer | F2–F3 incelemesi: sızıntı, CRS, birimler, metriklerin doğruluğu, dürüst dil | docs/reports/review-F3.md |

F3-1 tamamlanınca F3-2, F3-3 ve F3-4 aynı risk-modeler oturumunda sırayla da yapılabilir. Paralel yapılacaksa dosya sahipliğini ayır.

**K2 — Sonuçlar:** Orkestratör kullanıcıya şunları gösterir: kademe dağılımı, lift ve güven aralığı, taban çizgileri, 3 örnek iş paketi, senaryo karşılaştırması. Kullanıcı ağırlık ayarı isteyebilir.

## F4 — API ve arayüz (backend ve frontend paralel)
| ID | Ajan | İş | Çıktı |
|---|---|---|---|
| F4-1 | backend-dev | API sözleşmesi (docs/ARCHITECTURE.md), dışa aktarım, statik sunum, `scripts/serve.py`, testler | src/hatkalkani/api, export, tests/api |
| F4-2 | frontend-dev | Arayüz: önce mock JSON'la, sonra gerçek API'yle. Harita, iş listesi, detay, senaryo, doğrulama, TR/EN | web/ |
| F4-3 | qa-tester | Standart test turu + demo akışı ekran görüntüleri | docs/reports/qa-F4.md, docs/screens/ |
| F4-4 | code-reviewer | API ve arayüz için hafif inceleme (sayılar API'den mi geliyor, hata durumları) | docs/reports/review-F4.md |

**K3 — Demo provası:** Kullanıcı arayüzü kendisi dener. Geri bildirimler F5'e görev olarak girer.

## F5 — Demo cilası ve sunum malzemeleri
| ID | Ajan | İş |
|---|---|---|
| F5-1 | frontend-dev | Çevrimdışı mod: MapLibre yerel kopyası (web/vendor), yerel yedek altlık, CDN bağımlılığı yok. Projeksiyon testi. |
| F5-2 | backend-dev | Performans (ilk açılış < 3 sn), hata mesajları, demo verisi paketleme (gerekirse küçük `demo_data/` commit'i, ADR ile) |
| F5-3 | pitch-writer | docs/pitch/: SUNUM_AKISI.md (5 dk), DEMO_METNI.md (90 sn), SORU_CEVAP.md (en az 15 jüri sorusu), ETKI_HESABI.md (birimli, varsayımlar açık, düşük/orta/yüksek) |
| F5-4 | doc-writer | README çalıştırma talimatı, ATTRIBUTIONS eksiksiz, docs/SAHA_GORUSMELERI.md: 3 kurum tipi için sorular + geri bildirim kayıt şablonu (EDAŞ, OGM/Tarım ve Orman, sigorta/enerji yatırımcısı) |
| F5-5 | qa-tester | Temiz klon provası: yeni klasöre kopyala, `uv sync`, önbellekten pipeline, sunucu, demo akışı; süreleri ölç; internet kapalıyken tekrar |
| F5-6 | code-reviewer | Son inceleme: dürüstlük, atıflar, sunumdaki her sayının kaynağı |

**Final hazırlığı:** Faktör kaydı ve dışa aktarım kaydı sayesinde yeni bir faktör, eşik veya biçim 1–2 saatte eklenebilmeli. risk-modeler ve backend-dev bunun nasıl yapıldığını docs/reports/F5-genisletme.md'de 10 satırla anlatır.

## F6 — Final (15–16 Kasım)
- **15 Kas 13:00:** Kullanıcı "final başladı" der → `git tag final-start`. Bundan sonraki her değişiklik docs/FINAL_CHANGELOG.md'ye yazılır.
- **Saha görüşmeleri:** Kayıtları docs/SAHA_GORUSMELERI.md'ye girer. Orkestratör en az bir geri bildirimi göreve çevirir ve uygular.
- **16 Kas 13:00:** Teslim öncesinde qa-tester son turu çalıştırır ve sunum dosyasına final değişiklikleri bölümü eklenir.
