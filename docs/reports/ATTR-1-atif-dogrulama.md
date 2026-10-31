# ATTR-1 — Atıf ve lisans doğrulama (kısmi)

Tarih: 2026-10-30
Model: claude-haiku-5-5

## Sonuç
Dört kaynağın hiçbiri resmî sayfadan doğrulanamadı. Web erişimi (WebFetch ve WebSearch) "aylık harcama limiti" hatası döndü; limit 11:40 pm (Europe/Istanbul) civarında sıfırlanıyor. Bir Copernicus denemesi ayrıca ECONNREFUSED verdi. Bu nedenle `docs/ATTRIBUTIONS.md` değiştirilmedi.

## Yazma kısıtı
Görev `docs/ATTRIBUTIONS.md` dosyasının düzeltilmesini istiyor. Bu ajanın yazma izni listesinde (docs/reports/, docs/DATA_SOURCES.md, docs/REGULATION_NOTES.md "Ham bulgular", data/raw/_scout/) bu dosya yok. Dosya düzenlenmedi. Düzeltmeyi yapmak için izin verilmesi gerekiyor.

## Kaynak bazında durum

| # | Kaynak | Durum | Denenen | Sonuç |
|---|---|---|---|---|
| 1 | Copernicus DEM GLO-30 atıf + lisans | DOĞRULANMADI | WebFetch spacedata.copernicus.eu (CSCDA PDF) | ECONNREFUSED |
| 1 | (aynı) | DOĞRULANMADI | WebFetch dataspace.copernicus.eu/terms-and-conditions | Harcama limiti |
| 2 | Meta/WRI CHM v2 atıf, lisans, Maxar | DOĞRULANMADI | WebFetch registry.opendata.aws/dataforgood-fb-forests/ | HTTP 404 |
| 3 | NASA FIRMS atıf | DOĞRULANMADI | WebFetch firms.modaps.eosdis.nasa.gov/usfs/faq/ | Harcama limiti |
| 4 | Open-Meteo atıf + lisans | DOĞRULANMADI | WebFetch open-meteo.com/en/terms | Harcama limiti |
| - | Genel arama (Copernicus DEM) | DOĞRULANMADI | WebSearch | Harcama limiti |

## Mevcut ATTRIBUTIONS.md'deki doğrulanmamış satırlar (değişmedi)
- Copernicus DEM GLO-30: resmî atıf metni `[DOĞRULANMADI]`. Kayıt ibaresi "ESA/Copernicus" ayrıca doğrulanmalı.
- CHM v2: Maxar satırı `[DOĞRULANMADI]`. Lisans CC BY 4.0 olarak DATA_SOURCES.md'de yazılı, resmî sayfada teyit edilmedi.
- NASA FIRMS: atıf metni "NASA FIRMS (LANCE/EOSDIS)" tahmini; resmî öneri metni yok.
- Open-Meteo: "Weather data by Open-Meteo.com" ve CC BY 4.0 DATA_SOURCES.md'den alındı; resmî sayfa teyit edilmedi.

## Önerilen sonraki adımlar
1. Harcama limiti artırılınca ya da 11:40 pm sonrası aynı dört URL'yi yeniden dene.
2. Copernicus için alternatif resmî kaynak: `https://dataspace.copernicus.eu` ve `https://spacedata.copernicus.eu` (DEM dokümanları).
3. CHM v2 için Meta/WRI'nin resmî sayfası ya da `https://registry.opendata.aws/dataforgood-fb-forests/` (404 döndü; güncel adres kontrol edilmeli).
4. Düzeltmeyi uygulamak için `docs/ATTRIBUTIONS.md` yazma izni verilmeli.

## Çalıştırılan kontroller
- `Glob docs/reports/*` → mevcut raporlar listelendi.
- `.env` içeriği okunmadı; FIRMS_MAP_KEY kontrolü izin reddi nedeniyle yapılamadı. Bu görevde FIRMS anahtarı gerekmedi.

## 31 Eki yeniden deneme (ATTR-1b)

Tarih: 2026-10-31. Web çağrısı: 16 / 20. İndirme yok. .env okunmadı.
Kısıt notu: docs/ATTRIBUTIONS.md ve config/sources.yaml bu ajanın yazma izninde değil (config/ yasak). Metin değişiklikleri yapılmadı; aşağıdaki öneriler orkestratör/doc-writer tarafından uygulanmalı.

### Copernicus DEM GLO-30 resmî atıf metni: DOĞRULANDI
- Kaynak: https://dataspace.copernicus.eu/node/1306 (Copernicus Data Space, "Copernicus DEM" sayfası, Kullanım yükümlülükleri bölümü)
- Birebir (sayfadan, WebFetch ile alındı): "© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA"; "all rights reserved"
- Türev/uyarlanmış veri için: "produced using Copernicus WorldDEM-30" ile başlayan bildirim.
- Lisans: "The GLO-30 and GLO-90 datasets are available worldwide with a free license." (kaynak: https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM)
- Erişim tarihi: 2026-10-31.
- Not: Lisans PDF'i (https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM/resources/license/License-COPDEM-30.pdf) okunamadı (sıkıştırılmış PDF). ESA annex (spacedata.copernicus.eu) ECONNREFUSED verdi. Bu nedenle metin Copernicus Data Space sayfasından alındı; lisans PDF'i ile bir kez daha karşılaştırılması önerilir.
- Kayıt ibaresi: Earth Search `providers` alanında licensor "European Space Agency" (https://earth-search.aws.element84.com/v1/collections/cop-dem-glo-30). Earth Search `license` alanı "proprietary"; lisans bağlantısı: https://spacedata.copernicus.eu/documents/20126/0/CSCDA_ESA_Mission-specific+Annex.pdf (erişilemedi).
- AWS registry (https://registry.opendata.aws/copernicus-dem/) yalnızca "Copernicus Digital Elevation Model (DEM) was accessed on DATE from https://registry.opendata.aws/copernicus-dem." önerir; bu bir alıntı biçimi, resmî telif bildirimi değildir.

### Meta/WRI CHM v2 "Source imagery © Maxar" satırı: DOĞRULANAMADI (v2 için)
- v1 ibaresi registry'de mevcut: https://registry.opendata.aws/dataforgood-fb-forests/ sayfası "Source imagery for CHM © 2016 Maxar" (https://www.maxar.com/products/imagery-basemaps) ibaresini ve CC BY 4.0 lisansını (https://creativecommons.org/licenses/by/4.0/) veriyor. Erişim: 2026-10-31.
- Aynı sayfa yalnızca forests/v1/ yollarını listeliyor; v2 (dinov3_global_chm_v2_ml3) hakkında bölüm yok.
- Registry metninde yazım: "Meta and World Resources Institude (WRI) - 2024. High Resolution Canopy Height Maps (CHM)." ("Institude" yazımı WebFetch özetinden; birebir teyit edilmeli).
- v2 için kaynak denemeleri: https://dataforgood-fb-data.s3.amazonaws.com/forests/v2/ → HTTP 403; .../v2/global/dinov3_global_chm_v2_ml3/ → HTTP 403; .../README.md → HTTP 404.
- https://source.coop/tge-labs/meta-chm-v2: lisans "CC-BY-4.0. Underlying data © Meta / Data for Good; repackaging by Taylor Geospatial Engine Labs. See LICENSE"; "Source imagery" veya Maxar ibaresi YOK.
- https://arxiv.org/abs/2603.06382 (CHMv2, Brandt vd.): görüntü sağlayıcısı belirtilmiyor ("high-resolution optical satellite imagery").
- Sonuç: v2 satırında Maxar ibaresi kanıtlanmadı. Güvenli taslak: v2 için Maxar satırı yazılmadan [DOĞRULANMADI] kalmalı; v1 yedek için Maxar satırı kullanılabilir.

### Önerilen metinler (uygulanmadı)
- ATTRIBUTIONS.md satır 11 (Copernicus DEM): atıf metni "© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved" olabilir; kaynak https://dataspace.copernicus.eu/node/1306.
- config/sources.yaml DEM `attribution` alanı ("ESA/Copernicus") bu metinle değiştirilmeli (yetkili ajan).
- ATTRIBUTIONS.md satır 9 (CHM): Maxar ibaresi v2 için [DOĞRULANMADI] kalmalı; atıf kaynağı olarak registry metni "Institude" yazımıyla karşılaştırılmalı.
- ATTRIBUTIONS.md satır 21 DEM kısmı kapatılabilir; CHM v2 Maxar kısmı açık kalır.

### Çalıştırılan kontroller
- `uv run python -c "import yaml;..."` → yaml OK
- `uv run pytest tests/api -q` → 18 passed, 1 warning
