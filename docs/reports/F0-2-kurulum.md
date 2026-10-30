# F0-2 Kurulum raporu

Model: claude-sonnet-5-5

## Git
- `git init -b main`; `.env` ignore ediliyor (check-ignore OK). Kimlik: git config dolu.
- İlk commit: 87d9e3b `chore: initial project skeleton` (55 dosya). Hariç tutulanlar: docs/BASVURU_TASLAK.md, docs/pitch/EKIP.md, docs/reports/F0-*, docs/screens/F0-*, data/interim/*.html.

## Ortam
- uv 0.13.6 (resmî yükleyiciyle kuruldu, `C:\Users\merto\.local\bin`; Git Bash'te `export PATH="$HOME/.local/bin:$PATH"` gerekir)
- Python 3.12.16
- geopandas 1.2.0, rasterio 1.5.2, pystac-client 0.9.1, odc-stac 0.5.3, duckdb 2.0.0, fastapi 0.162.0
- `uv sync` başarılı; import testi "imports ok"; `uv run pytest -q` -> 1 passed

## context7 MCP
- Araçlar: `mcp__context7__resolve-library-id`, `mcp__context7__query-docs` (ikisi de yanıt verdi; kütüphane ID `/opendatacube/odc-stac`)
- `odc.stac.load(items, bands, *, groupby, resampling, dtype, chunks, ...)`:
  - `bbox`: (x0,y0,x1,y1), her zaman EPSG:4326 lon/lat kabul edilir.
  - `crs`: çıktı ızgarasının CRS'i; `x=,y=` kullanılırsa zorunlu. `geopolygon` verilirse kendi CRS'i yedek olur.
  - `resolution`: çıktı piksel boyutu (crs birimiyle); GeoBox `crs` + `resolution` ile oluşur.
  - `chunks`: örn. `{'x': 2048, 'y': 2048}`; verilirse Dask destekli tembel dizi döner.
