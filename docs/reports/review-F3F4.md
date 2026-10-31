# REV-F3F4: F3 (risk modeli) ve F4 (API, arayüz) birleşik inceleme

- **Gözden geçiren:** claude-opus-5-5 (Opus 5.5), kıdemli kod ve yöntem gözden geçireni
- **Tarih:** 2026-10-31
- **Kapsam:** `git diff aa9a0d8..HEAD` (8345d9f, abe3ebb). Model, özellikler, API, ingest/firms.py, ingest/chm_dates.py, betikler, web/, testler, MODEL_CARD, DECISIONS (ADR-009…013), F3-2/3/4 raporları ve `data/processed/izmir_menderes/` çıktıları.
- **web/ notu:** frontend-dev çalışma kopyasında doğrulama sekmesini değiştiriyor (commit edilmemiş). Satır numaraları HEAD'e göredir. Çalışma kopyasında düzeltilmekte olanlar ayrıca belirtildi.
- **Testler:** `uv run --offline --frozen pytest -q`: 215 test geçti. `uv run ruff check src tests scripts`: temiz.

## Özet
| Önem | Sayı |
|---|---|
| Kritik | 0 |
| Yüksek | 2 |
| Orta | 5 |
| Düşük | 12 |

Çekirdek hesaplar doğru. Metrik CRS'te mesafe, km/s dönüşümü, 300 m bina sayımı, as_of_used seçimi, Shapley toplamı, yüzdelik, NaN politikası, kademeler, lift ve binom aralıkları koddan beklenen değerleri veriyor. MODEL_CARD ve F3 raporlarındaki sayıları çıktılardan yeniden ürettim (aşağıdaki liste). API'de path traversal, arayüzde XSS bulunmadı. İki Yüksek bulgu da dürüstlükle ilgili: (1) "yalnız as_of öncesi veri" iddiası statik katmanlar için yanlış, (2) commit'li mock fikstürleri ve ekran görüntüleri uydurma, olumlu sonuçlar gösteriyor.

---

## Yüksek

### Y1. Backtest haritası as_of'tan sonra yayımlanmış statik katmanları kullanıyor; belgeler ve arayüz tersini söylüyor
- **Yer:**
  - `src/hatkalkani/model/backtest.py:187-205` (`check_no_leakage`)
  - `docs/MODEL_CARD.md:35`
  - `web/i18n.js:97` ve `:227` (HEAD, `val_hint`)
  - `src/hatkalkani/model/backtest.py:520-555` (limitations listesi)
- **Sorun:**
  - 2025-05-31 özellik setinde `wui_exposure`, Overture'ın **2026-10-21.0** sürümünden geliyor. Özellik meta verisi bunu `temporal_status = static_release_after_backtest_as_of` diye işaretliyor.
  - Segmentler (ve dolayısıyla "hat yakını olay" tanımı) **2026-10-30** tarihli OSM anlık görüntüsünden geliyor (`MODEL_CARD.md:26`).
  - `check_no_leakage` yalnız `max_time_used_utc` alanına bakıyor (`backtest.py:200-204`). Statik katmanlarda bu alan olmadığı için sızıntı sessizce geçiyor.
  - Buna karşın belgeler ve arayüz şunu söylüyor:
    - MODEL_CARD: "Her özellik yalnız as_of kesiminden önceki veriyi kullanır."
    - Arayüz: "Model yalnızca kesim tarihine kadarki veriyle çalıştırıldı."
  - `backtest.json` sınırlılıkları bu durumu anmıyor.
  - Sıfırdan farklı lift veren tek taban çizgisi ("Yalnız bina yakınlığı", üst %20'de 2/2, lift 5,0) tam da bu katmana dayanıyor.
  - Spec ilkesi ("as_of tarihinden sonraki hiçbir veri özelliklere giremez") harfiyen ihlal ediliyor. Etkisi büyük olasılıkla küçük, ancak iddia yanlış.
- **Kanıt:**
  ```
  uv run python -c "import json;m=json.load(open('data/processed/izmir_menderes/features_2025-05-31.meta.json',encoding='utf-8'));p=m['provenance']['wui_exposure'];print(p['overture_release'],p['temporal_status'],p.get('max_time_used_utc'))"
  -> 2026-10-21.0 static_release_after_backtest_as_of None
  grep -n "Her özellik yalnız" docs/MODEL_CARD.md        -> 35
  git show HEAD:web/i18n.js | grep -n "val_hint"         -> 97, 227
  ```
- **Öneri:**
  1. `check_no_leakage` statik katmanları ayrı bir listeye toplasın: `temporal_status` "after_…" olanlar ile sürüm/erişim tarihi ≥ kesim olanlar. Bu liste `backtest.json`'a `leakage.static_after_as_of` alanı ve bir limitation satırı olarak yazılsın. Bu durumu sınayan bir test eklensin.
  2. MODEL_CARD §2 ve `val_hint` düzeltilsin: "Zamanla değişen veriler (FIRMS, S2, rüzgâr) kesimden öncedir; bina (Overture 2026-10) ve hat (OSM 2026-10) katmanları güncel anlık görüntüdür."

### Y2. Commit'li mock fikstürleri ve ekran görüntüleri, gerçek sonuçla çelişen uydurma olumlu sayılar gösteriyor
- **Yer:**
  - `web/mock/backtest.json` (HEAD; tek satır)
  - `web/mock/scenario.json` (HEAD ve çalışma kopyası)
  - `web/mock/scenario_dates.json` (HEAD)
  - `docs/screens/04-dogrulama-mock.png`, `docs/screens/03-senaryo-mock.png` (8345d9f)
- **Sorun:**

  | Çıktı | Mock (uydurma) | Gerçek |
  |---|---|---|
  | Doğrulama | 12 olay; üst %10'da lift 3,3× [1,4–5,1]; üst %20'de 2,5× [1,3–3,8]; sezon 06-01…**10-31**; olay noktaları hatların üstünde | n = 2, lift 0, binom aralığı [0; 8,37]; sezon …09-30 |
  | Senaryo | İlçe geneli 60.825 bina; hedefli 18,4 km, 7.319 bina, risk payı %26 | 3.469 bina; hedefli 83,4 km, 3.032 bina, %92 |
  | Senaryo günü hamleleri | 58,0 / 74,5 / 66,2 / 49,8 | 54,7 / 71,3 / 83,5 / 62,3 |

  - İki ekran görüntüsü de bu uydurma sayıları gösteriyor. "MOCK VERİ" bandı görünüyor, ama görüntü kırpılır ya da başvuruda kullanılırsa uydurma bir doğrulama ve kazanç iddiası olur. `docs/BASVURU_TASLAK.md:84` docs/screens/'ten görüntü bekliyor.
  - Çalışma kopyasında backtest mock'u gerçek değerlere çekilmiş. scenario mock'u hâlâ 60.825 bina gösteriyor.
- **Kanıt:**
  ```
  git show HEAD:web/mock/backtest.json | head -c 180
  -> {"as_of": "2025-05-31", "season": "2025-06-01..2025-10-31", "n_events": 12, "top10": {"share": 0.33, "expected": 0.1, "lift": 3.3, "ci95": [1.4, 5.1]}...
  grep -o '"buildings": [0-9.]*' web/mock/scenario.json | head -2   -> 60825.0, 7319.0
  git log --format=%h -- docs/screens/04-dogrulama-mock.png        -> 8345d9f
  ```
- **Öneri:**
  1. `03-senaryo-mock.png` ve `04-dogrulama-mock.png` silinsin ya da gerçek API ile yeniden çekilsin.
  2. Mock fikstürleri `data/processed/` çıktılarından bir betikle üretilsin (gerçek sayılar), ya da açıkça yer tutucu olsun (ör. tüm metrikler `null`).
  3. Mock modunda haritaya da filigran konsun.

---

## Orta

- **O1. CHM tarih ifadeleri birbiriyle çelişiyor ve bir kısmı eskimiş.**
  - **Eskimiş "tarih yok" ifadeleri:** Veri artık 925/925 segmenti tarihliyor (2016-07-22…2020-02-18; `chm_acq_segment.meta.json`, `risk_*.meta.json` → `chm_dates`). Buna karşın şu yerler hâlâ "CHM v2'nin tarihi yok" diyor:
    - `web/i18n.js:119` ve `:249` (`about_n4`, Hakkında sekmesinde her zaman görünüyor)
    - `web/i18n.js:66` ve `:196` (`chm_unknown`)
    - `api/store.py:27-28`
    - `config/sources.yaml:12` (`/api/meta/sources` ile servis ediliyor)
    - `ingest/chm.py:598` (özellik meta verisine taşınıyor)
  - **Tarih aralığı farkı:** `MODEL_CARD.md:27,43` ve `backtest.py:531,550` "…2020-02-19" diyor. Segment düzeyindeki veri ise 2020-02-18'de bitiyor. 02-19 değeri v1 referans aralığından geliyor; metin veriden üretilmiyor, elle yazılmış.
  - **Öneri:**
    - `about_n4`'ü "görüntüler 2016–2020 tarihli; parça tarihi detayda" diye düzelt.
    - Limitation metnini `rmeta["chm_dates"]` alanından üret.
    - `sources.yaml` notunu ve store'daki yedek notu ("bu parça için tarih bulunamadı") güncelle.
- **O2. Dejenere bootstrap aralığı güven aralığı gibi sunuluyor.**
  - `backtest.json` içinde `top10/top20.ci95 = [0, 0]` var (k = 0).
  - HEAD arayüzü bunu "Lift için %95 güven aralığı 0,0 – 0,0" diye ve bir çubukla gösteriyor (`app.js:566-575`, `i18n.js:106,236`). Bu, kesinlik izlenimi veriyor.
  - Çalışma kopyası düzeltiyor (binom aralığı öne alınıyor, "dejenere" etiketi ve n<5 etiketi ekleniyor); commit'ten sonra doğrulanmalı.
  - **Öneri:** Backend'de k∈{0,n} iken `ci95: null` ve `ci95_note: "degenerate"` yaz; böylece her tüketici doğru okur.
- **O3. Senaryo haritası başka bir as_of'un kademe renklerini gösteriyor.**
  - Senaryo 2025-05-31 kademeleriyle hesaplanıyor (`inputs.as_of_used`). Alttaki segment katmanı ise 2026-10-30'da kalıyor (`app.js:456-509`; doğrulama sekmesi bu geçişi yapıyor, senaryo yapmıyor).
  - İki harita arasında kritik örtüşmesi 0,696. Bu yüzden aday olan bir segment haritada orta veya düşük renkte görünebilir. Tıklanınca açılan detay da 2026 verisini gösterir.
  - **Öneri:** `runScenario` sonrasında `loadSegments(r.inputs.as_of_used)` çağır ve `map-asof` rozetini göster; sekmeden çıkınca geri dön.
- **O4. Seçim yanlılığı sınırlılıklarda yazmıyor.**
  - Pilot ilçe 29.06.2025 yangını ve 2024–25 yangınları gerekçesiyle seçildi (ADR-006). Senaryo adayları da o yangının günleri.
  - Backtest aynı 2025 sezonunu kullanıyor; yani test bölgesi sonuca bakılarak seçildi. Sonuç nötr olduğu için bugünkü sayılar etkilenmiyor.
  - **Öneri:** MODEL_CARD §7/§8'e ve `limitations_*` listesine ekle. Çok yıllı backtest'te 2025'i ayrı raporla.
- **O5. Arayüzde abartı.**
  - `i18n.js:118` "EDAŞ dağıtım hattı verisi gelirse aynı yöntemle çalışır" ve `:248` "the method works unchanged on a utility's distribution GIS file".
  - Bu ifade MODEL_CARD §1/§8 ile çelişiyor ("yeniden test edilmelidir"; açıklık bantları doğrulanmadı).
  - **Öneri:** "aynı yöntemle çalıştırılabilir; sonuçlar yeniden test edilmelidir".

## Düşük
- **D1. Beklenen değer (yöntem notu).** Sayıya dayalı `expected`, segmentlerin farklı "yakalama alanını" hesaba katmıyor. İlçe ∩ 500 m tamponda 20 m'lik ızgarayla alan payını hesapladım: üst %10 için 0,0965 (sayı payı 0,1005), üst %20 için 0,1930 (0,2000). Oran 0,96; sapma küçük ve muhafazakâr yönde. Geniş AOI'de veya çok yıllı testte alana dayalı sıfır dağılımı ek taban çizgisi olarak verilebilir.
- **D2. Ön kayıt doğrulanamıyor.** "Sonuç görülmeden kayıtlı" iddiası depodan doğrulanamıyor: ADR-013, `backtest` config bloğu, `type` filtresi, kod ve sonuç raporu aynı commit'te (abe3ebb). Öte yandan 500 m eşiği ilk iskelet commit'inden (c423a81) beri sabit ve `type` filtresi sezonda 0 satır dışladı (pratik etkisi yok). İfadeyi buna göre yumuşat; ileride protokolü ayrı commit veya etiketle kaydet.
- **D3. `routes.py` küçük hataları.**
  - `:44`: ipucu `--stage model` öneriyor; böyle bir aşama yok.
  - `:46-50`: biçim denetimi üyelik denetiminden sonra geliyor. Bozuk bir as_of 404 dönüyor; 422 dalı ölü kod.
- **D4. Koda gömülü sabitler.**
  - Senaryo varsayılanları 50 ve `yuksek`: `routes.py:218-219`, `app.py:44`. Config'teki `scenario.*` kullanılmıyor; şu an değerler eşit.
  - `routes.py:252`: `events_2025.geojson` sabit yazılmış.
  - `backtest.py:61`: `CASE_DAY`.
  - Bunlar config'ten okunmalı.
- **D5. Senaryo hata kodu.** `ScenarioDataError` (RuntimeError) 500 döndürüyor ve yanıtta yalnız sınıf adı var (`routes.py:231-238`, `app.py:91-96`). 503 ve mesaj dönmeli.
- **D6. Türkçe ek hatası.** `scenario.py:306`: "%66'si" üretiyor, doğrusu "%66'sı". Eki sayıya göre seç ya da cümleyi "%66 oranında" diye kur.
- **D7. Orta gerilim ifadesi.** `MODEL_CARD.md:21` "OSM'de bu ilçede orta gerilim hattı yok" diyor; segmentlerde 0,43 km `power=minor_line` var (voltage_level `mv`, varsayım). "Etiketli OG hattı yok" demek daha doğru.
- **D8. F3-2 raporu eskimiş.** F3-2-skor.md:162'deki örnek iş paketi değerleri yeniden skorlamadan önceki değerler (risk_max 73,51; güncel çıktı 73,48). :155'teki etiket de eski ("Rüzgâra açıklık"). Not düşülmeli.
- **D9. FIRMS NRT önbellek süresi.** `firms.py:60` `NRT_TTL_DAYS = 14`: 13 Kasım'dan sonra `--stage ingest/all` ağ bağlantısı ve `FIRMS_MAP_KEY` ister. Çevrimdışı demo için score/scenario/backtest aşamaları yeterli; bu, STATUS'a yazılmalı.
- **D10. Config tutarlılığı.** `backtest._rankings` içindeki strike_tall varyantı ve doğrusal birleştirme taban çizgisi o anki config ile skorluyor. Risk dosyasındaki config anlık görüntüsüyle (`rmeta["config"]`) eşitlik denetlenmiyor.
- **D11. "Kapsanan risk oranı" anlamı.** Bu oran, skor × uzunluk toplamının payıdır; olasılık ya da risk miktarı değildir. Arayüze bir açıklama ya da tooltip eklenmeli.
- **D12. Doğrulama sekmesi ayrıntıları (çalışma kopyası).** Vaka tablosu kümenin `inside_aoi = false` olduğunu (ilçe sınırının 263 m dışında) göstermiyor. `n_events < 5` eşiği arayüzde sabit yazılmış.

---

## Odak sorularına yanıtlar
1. **Sızıntı:**
   - Zamanla değişen veriler as_of öncesinde kalıyor: fire_history 2025-05-28 11:54 UTC, S2 2025-05-31 09:10 UTC, rüzgâr 2024-09-30. Kesim 2025-05-31 21:00 UTC.
   - Statik bina ve hat katmanları as_of sonrasına ait (Y1).
   - `type` filtresi ADR-013 ile aynı commit'te geldi. Sezonda 0 tespit dışladı; fire_history'den 6 deniz tespiti düştü (D2).
   - CHM 2016–2020 ifadesi özünde doğru (5,3–8,9 yıl); ancak bitiş günü ve "tarih yok" metinleri hatalı (O1).
2. **Metrikler:**
   - Lift, beklenen değer (sayı ve uzunluk payı), bootstrap (B = 10000, sabit tohum, eşleştirilmiş örnekler), Clopper–Pearson ve tek yönlü p değeri doğru hesaplanıyor.
   - Üst küme tanımı `pct ≥ 1 − pay` (ADR-013 ile tutarlı).
   - Kümeleme tek bağlantılı: ≤1000 m ve ≤2 yerel gün.
   - Tüm mesafeler EPSG:32635'te hesaplanıyor. Yeniden üretilen değerler: E2025_007 34,2 m ve yüzdelik 0,183; E2025_035 363,8 m ve 0,650; vaka 2611 m ve sınırın 262,6 m dışında.
3. **Senaryo:**
   - m/s × 3,6 dönüşümü doğru: ingest km/s istiyor ve m/s'ye çeviriyor.
   - Bina sayımı: temsil noktası, metrik CRS'te `dwithin` 300 m (sınır dahil).
   - Kesinti birimi OSM way.
   - as_of_used, gün tarihinden kesin önceki en son harita.
   - Risk payı uzunluk ağırlıklı (ADR-012 ile tutarlı).
4. **Skor:**
   - Shapley toplamı risk − 50 (testli).
   - Orta-sıra yüzdelik.
   - NaN politikası belgeli: `all_water` → 0, diğer belgeli nedenler → 0,5; nedensiz NaN hata verir.
   - Kademe dağılımı 46/139/278/462.
5. **API ve arayüz:**
   - `as_of`, `format`, `segment_id` ve `date` yalnız sözlük anahtarı olarak ya da regex/desen denetimiyle kullanılıyor. İstek sırasında dosya yolu kurulmuyor; path traversal yok.
   - API'den gelen her veri `esc()` ile basılıyor; XSS yok. Bağlantılardaki `href` için `javascript:` engeli yok, ancak kaynak güvenilir `config/sources.yaml`.
   - Ekrandaki sayılar API'den geliyor. İstemcide türetilen yalnız "kesilmeyen km" ve "kurtulan bina" farkları var.
   - 503 ve 404 durumları "henüz üretilmedi" iletisiyle ele alınıyor.
6. **Dürüst dil:**
   - MODEL_CARD, F3-3 ve note_tr/en ölçülü bir dil kullanıyor; vakada "bildirildi" dili var.
   - Sorunlar: Y1, Y2, O1, O5.
7. **Lisans ve atıf:**
   - OpenFreeMap atıfı hem MapLibre atıf denetiminde hem altbilgide var. MapLibre BSD-3 lisans dosyası vendor/ altında.
   - `sources.yaml` ile ATTRIBUTIONS tutarlı; Open-Meteo'nun ticari kullanım kısıtı yazılı.
   - Eksik atıf yok. CHM notu eskimiş (O1).

## Çıktılardan yeniden üretilen sayılar (doğru)
- **Hatlar:** 925 segment; 92,4 km; 17 hat; en uzun hat 16,48 km; uzunluğun %99,5'i `power=line`, %66'sı ≥154 kV.
- **Risk haritaları:**
  - Kademeler 46/139/278/462.
  - Skor min/medyan/maks: 2025 haritasında 16,5/48,8/78,9; 2026 haritasında 19,3/49,0/77,6.
  - İş paketi: 72 (18,5 km) ve 76 (18,4 km).
  - İki as_of arasında ρ = 0,953; kritik örtüşmesi 0,696.
- **CHM:** baskın yıl dağılımı 30/23/15/630/227; %93'ünde baskın yıl 2019 veya 2020.
- **Senaryo (29 Haziran 2025):** ilçe geneli 92,4 km ve 3469 bina; hedefli 83,4 km, 3032 bina, risk payı 0,917; segment birimiyle 18,46 km, 993 bina, 0,260.
- **Backtest:** 788 tespit, 36 küme, ilçe içinde 10, hat yakını 2; lift 0; binom aralığı [0; 8,37] ve [0; 4,21].

## Test kapsamı
- Kritik mantık iyi test edilmiş: sızıntı, Shapley'in permütasyon tanımına eşitliği, kademe oranları, iş paketi birleştirme, senaryonun kaba kuvvet hesabıyla karşılaştırılması, birim (×3,6) ve önbellek.
- Eksikler:
  - Statik katman as_of'tan sonraysa uyarı ya da hata veren bir test (Y1).
  - Route varsayılanlarının config ile eşitliği (D4).
  - Limitation metnindeki CHM aralığının veriyle eşitliği (O1).
  - Mock fikstürlerin gerçek çıktılarla tutarlılığı (Y2).
