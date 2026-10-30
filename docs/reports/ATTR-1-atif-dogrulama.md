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
