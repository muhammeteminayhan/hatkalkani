# FIX-F3: REV-F3F4 model bulgularının düzeltilmesi (backtest beyanı, karar alanı, metinler)

- **Model:** claude-opus-5-5 (Opus 5.5), risk-modeler
- **Tarih:** 2026-10-31
- **Kapsam:** REV-F3F4 bulguları Y1, O1, O2, O4, D2, D6 ve D7 (model tarafı). Skor, ağırlık ve kademeler değişmedi.
- **Kod:**
  - `src/hatkalkani/model/backtest.py` (şema `backtest-0.2`),
  - `src/hatkalkani/model/scenario.py` (yalnız `note_tr` cümlesi).
- **Testler:**
  - `tests/model/test_backtest.py` (9 → 16 test),
  - `tests/model/test_backtest_real_outputs.py` (yeni, 4 test),
  - `tests/model/test_scenario.py` (+4 parametreli test; sözleşme testine ek denetim).
- **Yeniden üretilenler:** `--stage scenario` ve `--stage backtest` çalıştırıldı.
  - `backtest.json` ve `events_2025.geojson` yeniden yazıldı.
  - `scenario_2025-06-29.json` içinde yalnız `note_tr` değişti.
  - `scenario_dates.json` bayt düzeyinde aynı kaldı.

## 1. Değişmeyenler (doğrulandı)
- **Dosya özetleri:** Şu dosyaların sha256 değeri çalıştırmadan önce ve sonra aynı:
  - `risk_2025-05-31.parquet` (`4cba2a8c…`), `risk_2026-10-30.parquet` (`fb07de9a…`),
  - risk meta ve GeoJSON dosyaları, iş paketleri (CSV/GeoJSON/GPKG),
  - `features_*.parquet` ve meta dosyaları, `segments.parquet`.
- **Sayılar:** backtest.json'daki her sayı eski dosyayla aynı. Değişen yalnız dejenere `ci95` alanları; 36 blokta `[0, 0]` ya da `[4,97; 4,97]` yerine `null` yazılıyor.
- **config/risk_weights.yaml:** Dokunulmadı. Hash'i risk meta verisinde kayıtlı (`09f04995…`).

## 2. Ana çıktıların özeti (değişmedi)
| Harita | kritik / yüksek / orta / düşük | Skor min / medyan / max | İş paketi |
|---|---|---|---|
| 2025-05-31 (backtest) | 46 / 139 / 278 / 462 | 16,5 / 48,8 / 78,9 | 72 (18,5 km) |
| 2026-10-30 (güncel) | 46 / 139 / 278 / 462 | 19,3 / 49,0 / 77,6 | 76 (18,4 km) |

- **Olaylar:** 788 VIIRS tespiti, 36 küme. Vekili ilçe içinde olan 10 olay var; bunların 2'si hatta ≤500 m.
- **Model:**
  - Üst %10: 0/2, lift 0, beklenen pay 0,1005. Kesin binom lift aralığı [0; 8,37].
  - Üst %20: 0/2, lift 0, beklenen pay 0,200. Kesin binom lift aralığı [0; 4,21].
  - Bootstrap aralığı iki kümede de dejenere (`ci95: null`).
- **Yalnız bina yakınlığı taban çizgisi:**
  - Üst %10: 1/2, lift 5,03. Bootstrap [0; 10,05], binom [0,13; 9,93].
  - Üst %20: 2/2, lift 4,97, p = 0,040. Bootstrap dejenere; binom aralığı [0,79; 4,97].
  - 14 karşılaştırma içinde bu sonuç gürültüdür. Ayrıca as_of sonrası bina katmanına dayandığı için iyimser olabilir (Y1).
- **Senaryo (2025-06-29):**
  - İlçe geneli: 92,4 km, 3469 bina.
  - Hedefli: 83,4 km, 3032 bina, risk payı 0,917.

## 3. backtest.json yeni alanlar (arayüz ve API için)
- **`verdict`:** `{informative, n_events, min_events, reason_tr, reason_en}`. Pilotta `informative = false`, `n_events = 2`, `min_events = 38`.
- **`leakage`:** `{cutoff_utc, time_varying_before_cutoff, static_after_as_of, note_tr, note_en}`.
  - `time_varying_before_cutoff`: `[{layer, max_time_used_utc}]`. Pilotta fire_history 2025-05-28, fuel_dryness 2025-05-31, wind_exposure 2024-09-30.
  - `static_after_as_of`: `[{layer, label_tr, label_en, source, release, release_date, used_by, basis}]`. `used_by` bir dizidir.
  - Pilotta beyan edilen katmanlar:

    | layer | release | used_by |
    |---|---|---|
    | `buildings` | 2026-10-21.0 | wui_exposure, baselines.buildings |
    | `lines` | 2026-10-30 | segments, all_factors, near_line_events |
    | `boundary` | 2026-10-30 | segments, event_universe |
- **`ci95_note`:** Her `top10`/`top20` bloğunda var; taban çizgileri ve duyarlılık blokları dahil. Kural: `ci95` tam olarak `ci95_note` dolu olduğunda `null`'dır.
  - `"degenerate"`: k ∈ {0, n}; bu durumda `ci95_binomial` okunmalı.
  - `"no_events"`: n = 0.
  - `"empty_top_set"`: sıralamanın üst kümesi boş. Yalnız sentetik verideki eşit değerlerde görülür.
- **Metin değişiklikleri:**
  - `limitations_tr/en` yeni satırlar: statik katmanlar ve bina taban çizgisi uyarısı, seçim yanlılığı, kayıt ifadesi.
  - CHM satırı artık veriden üretiliyor: 2016-07-22…2020-02-18, as_of'tan 5,3–8,9 yıl önce.
  - `sensitivity_line_distance.label_tr/en` artık "önceden kayıtlı" demiyor.
  - `schema_version` `backtest-0.2` oldu.

## 4. Karar eşiği: MIN_EVENTS_INFORMATIVE = 38 (gerekçe)
- **Soru:** Test, model iyi olsaydı bunu görebilecek miydi?
- **Ölçüt:** Önceden kayıtlı iki kümeden olay gereksinimi daha az olanı, üst %20'dir. Operasyonel olarak anlamlı en küçük etki lift 2'dir: üst %20, hat yakını olayların %40'ını yakalar. Eşik, tek yönlü kesin binom testinin (α = 0,05) bu etkiyi en az %80 güçle saptadığı olay sayısıdır.
- **Neden 38:** Kesin binom gücü n'ye göre testere dişi çizer (n = 35'te 0,805, 37'de 0,778). Gücün bir daha 0,80'in altına düşmediği ilk n, 38'dir. Test bunu n = 2…200 aralığında yeniden hesaplıyor.

  | n | 2 | 10 | 20 | 30 | 35 | 37 | 38 | 40 | 50 |
  |---|---|---|---|---|---|---|---|---|---|
  | Güç (lift 2, üst %20) | 0,16 | 0,37 | 0,58 | 0,71 | 0,81 | 0,78 | 0,81 | 0,87 | 0,90 |
- **Sınırlar:**
  - n = 38'de üst %10 kümesinde lift 2'nin gücü yalnız 0,50'dir; lift 3 için 0,92'dir. Yani "bilgi verir" kararı, küçük etkilerin de görüleceği anlamına gelmez.
  - Eşik 2025 sonucuna bakılmadan da aynı çıkar; bir güç hesabıdır. n = 2 olduğu için makul her eşikte karar "bilgi vermiyor"dur.
- **Kod mu, config mi:** Eşik kodda adlandırılmış bir sabittir; görev tanımı böyle istedi. config/risk_weights.yaml'a eklenseydi dosyanın risk meta verisinde kayıtlı hash'i bayatlardı.

## 5. Kalan ve kapsam dışı
- **config/risk_weights.yaml:42 yorumu:** Hâlâ "sonuç görülmeden önce kaydedildi" diyor. Config hash'i bayatlamasın diye dokunulmadı; bir sonraki yeniden skorlamada düzeltilmeli.
- **Özellik meta verisi (CHM):** CHM için hâlâ `temporal_status: undated_static_baseline` yazıyor ve `image_dates` alanı eski "v2 tarih yok" metnini taşıyor. Düzeltmek features aşamasını yeniden çalıştırmayı gerektirir; bu görevde yasaktı. Backtest, CHM tarihini risk meta verisindeki `chm_dates` alanından okuyor.
- **Başka ajanların dosyaları (bu görevde dokunulmadı):**
  - `web/i18n.js` `val_hint` ve `about_n4` (O1, Y1),
  - `api/store.py:27-28`, `config/sources.yaml:12`, `ingest/chm.py:598`.
- **Çok yıllı backtest için hazırlık:**
  - Statik katman kuralı WorldCover'ı (`static_2021`) ve CHM görüntü tarihlerini de denetliyor. 2021'den önceki bir as_of için WorldCover 2021 ve 2019–2020 CHM görüntüleri otomatik olarak beyan edilir (test edildi).
  - Bu katmanlar o testte yangın sonrası arazi örtüsü sızıntısı taşıyabilir. Yeni protokol ADR'si bunu ele almalı.
