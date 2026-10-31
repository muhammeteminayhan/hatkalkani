# CHM-META: CHM v2 karo metadata tarih alanı

Tarih: 2026-10-31. Model: claude-haiku-5-5. Erişim: anonim S3 (curl).

## Bakılan yollar
- `https://dataforgood-fb-data.s3.amazonaws.com/forests/v2/global/dinov3_global_chm_v2_ml3/` (liste, 200)
- `.../metadata/` (liste, ilk 1000 anahtar; sayfalı değil)
- `.../metadata/1221003{102,103,120,121}.geojson` (liste ve range okuma)
- `.../chm/<tile>.tif` HEAD: 4 Menderes karosu için 200
- `.../tiles.geojson` HEAD ve range (58,9 MB; tam indirilmedi)

## Gerçek komutlar (kısaltılmış çıktı)
`curl -s "$B/?list-type=2&prefix=$P&delimiter=/"`
```
<Prefix>.../dinov3_global_chm_v2_ml3/chm/</Prefix>
<Prefix>.../dinov3_global_chm_v2_ml3/metadata/</Prefix>
<Key>.../dinov3_global_chm_v2_ml3/tiles.geojson</Key>
```
`curl -s "$B/?list-type=2&prefix=$M1221003102"`
```
<Key>.../metadata/1221003102.geojson</Key> <Size>8173414</Size>
```
`curl -s -r 0-2047 "$B/.../metadata/1221003102.geojson"` (kısaltılmış)
```
{"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"acq_date": "2020-02-08"}, "geometry": {"type": "Polygon", ...
```

## Bulunan metadata dosya türleri
- `metadata/`: yalnızca `.geojson` (ilk 1000 anahtarda 999 adet). Her dosya bir FeatureCollection; her Feature bir görüntü ayak izi (Polygon).
- Tek özellik alanı: `properties.acq_date` (YYYY-MM-DD). Örneklerde başka alan yok.
- `tiles.geojson` (üst düzey): yalnızca `properties.tile` ve geometri. İlk 512 KB'ta `acq_date` yok.

## Menderes karoları: acq_date (örneklenmiş)
- 1221003102 (8,2 MB): 2020-02-08, 2019-09-19, 2019-07-21
- 1221003103 (8,7 MB): 2020-02-18, 2019-09-11, 2019-10-21, 2019-08-06
- 1221003120 (15,2 MB): 2020-02-19, 2019-03-16, 2016-07-22, 2018-08-23
- 1221003121 (14,1 MB): 2019-05-17, 2019-09-11, 2020-02-16, 2019-03-10

Karo başına birden çok tarih var (mozaik). Tek bir "görüntü yılı" yok. Aralık 2016-07-22..2020-02-19; chm_meta.json'daki aralıkla aynı uçlar.

## Sonuç: TARİH VAR (ayak izi başına, örneklenmiş)
- Tam sayım yapılmadı: 4 dosya toplam 46 MB, 20 MB sınırını aşıyor. Her karoda 5 adet 512 KB örnek alındı.
- Çelişki: chm_meta.json "unknown" diyor ve DATA_SOURCES.md "v2 karolarında tarih yok" diyor. Bu bulgu ikisiyle çelişiyor. Düzeltme bu görevde yapılmadı (kapsam dışı).

## İndirme ve temizlik
- Toplam indirme yaklaşık 10,4 MB. Geçici örnek dizini (data/raw/_scout/chm_meta_probe) silindi.
- Fact-Forcing Gate bir kez `rm -rf` komutunu durdurdu. Gereksinimler yazılıp aynı komut yeniden çalıştırıldı.
