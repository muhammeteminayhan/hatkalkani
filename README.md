# HatKalkanı

Elektrik dağıtım hatlarından kaynaklanan orman yangını riskini 100 m'lik hat parçası düzeyinde puanlayan karar destek aracı. COP31 İklim Teknolojileri Creathonu için geliştiriliyor.

## Ne yapar

- **Koridor risk haritası:** 0–100 skor ve skoru yükselten 3 neden
- **Budama/drone iş emri listesi:** CSV, GeoJSON ve GeoPackage
- **Önleyici kesinti senaryosu:** rüzgârlı günde ilçenin tamamı yerine yalnızca riskli hatlar
- **Geriye dönük test:** 2025 yangın sezonu

Pilot ilçe: İzmir Menderes (`izmir_menderes`). Senaryo ve geriye dönük test aşamaları şu anda ekleniyor; hazır olmayan çıktılar arayüzde "henüz hesaplanmadı" olarak görünür.

## Claude Code ile çalışma
Bu depo, Claude Code masaüstünde çok ajanlı çalışmak üzere hazırlanmıştır.

1. Önce `MANUAL_TASKS.md` dosyasındaki "Başlamadan önce" adımlarını tamamlayın.
2. `KICKOFF_PROMPT.md` dosyasındaki ilk mesajı ana oturuma yapıştırın.
3. Sonraki oturumlarda aynı dosyadaki kısa devam mesajını kullanın.

| Dosya | İçerik |
|---|---|
| `CLAUDE.md` | Ana oturumun (orkestratör) protokolü ve model yönlendirme tablosu |
| `.claude/agents/` | 10 alt ajan; her birinin modeli ve effort'u burada |
| `.claude/skills/` | Ajanlara önceden yüklenen bilgi paketleri ve `/durum` komutu |
| `docs/PLAN.md` | Fazlar, görevler, kabul kriterleri, kontrol noktaları |
| `docs/STATUS.md` | Canlı durum panosu |

## Gereksinimler

| Gereksinim | Ayrıntı |
|---|---|
| Python | 3.12 (`pyproject.toml`: `>=3.12,<3.14`). Geliştirme ortamı 3.12.16 (`docs/STATUS.md`, F0-2) |
| uv | Bağımlılık ve çalıştırma aracı. Kurulum: https://docs.astral.sh/uv/ . Geliştirmede 0.13.6 kullanıldı |
| Disk alanı | [DOĞRULANACAK] Ham ve ara veri boyutu ölçülmedi |
| İnternet | Yalnızca veri indirme için. Sunucu çalışırken ağ çağrısı yapmaz |
| FIRMS_MAP_KEY | Ücretsiz NASA FIRMS anahtarı: https://firms.modaps.eosdis.nasa.gov/api/map_key/ . Anahtar `.env` dosyasına yazılır; değeri bu README'ye, koda veya sohbete yazılmaz |
| İşletim sistemi | Hedef Windows ve macOS. Geliştirme Windows 11'de yapıldı (`docs/STATUS.md`, F0-4) |
| Node.js | Uygulama için gerekmez; yalnızca Playwright MCP testleri için |

## Hızlı başlangıç

> Bu adımlar temiz bir makinede henüz denenmedi: **doğrulanmadı**.

1. Depo klasöründe bir terminal açın ve bağımlılıkları kurun:

```
uv sync
```

2. `.env.example` dosyasını `.env` adıyla kopyalayın ve `FIRMS_MAP_KEY` değerini kendi anahtarınızla doldurun. `.env` git'e girmez; anahtarı kimseyle paylaşmayın.

3. Veri hattını baştan sona çalıştırın:

```
uv run python scripts/run_pipeline.py --aoi izmir_menderes --stage all
```

Sonunda `MANIFEST validation OK` satırı görünmelidir.

4. Sunucuyu başlatın:

```
uv run python scripts/serve.py
```

5. Tarayıcıda açın: http://127.0.0.1:8000
   Mock veriyle denemek için: http://127.0.0.1:8000/?mock=1

6. Testleri çalıştırın:

```
uv run pytest
```

Ağ gerektiren testler varsayılan çalıştırmada atlanır.

### İlk çalıştırma ve önbellek

- **İlk çalıştırma uzundur**, çünkü veri indirilir. FIRMS'in ilk indirmesi yaklaşık 25 dakika sürdü (`docs/STATUS.md`, F2-5). Toplam süre: [DOĞRULANACAK]
- **Sonraki çalıştırmalar önbellekten gelir.** Önbellekten tüm ingest 29,2 sn; features 13,6 sn; score 3,0 sn (`docs/STATUS.md`, F2-6, F3-1, F3-2).

### Pipeline seçenekleri

- `--stage ingest | features | score | all`: `features` ve `score` önceki aşamaların çıktılarını bekler.
- `--only <modül>`: yalnızca ingest aşamasında. Modüller: `boundary`, `lines`, `segments`, `sentinel2`, `dem`, `worldcover`, `chm`, `buildings`, `firms`, `weather`.
- `--force`: seçili ingest çıktılarını silip yeniden üretir.

```
uv run python scripts/run_pipeline.py --aoi izmir_menderes --stage ingest --only firms
```

Sunucu seçenekleri `--host`, `--port` ve `--aoi`'dir:

```
uv run python scripts/serve.py --host 127.0.0.1 --port 8001
```

## Arayüz

- **Sol panel, sekmeler:** İş listesi · Senaryo · Doğrulama · Hakkında. Senaryo ve Doğrulama, ilgili dosyalar yoksa "henüz hesaplanmadı" gösterir (ADR-011).
- **Orta:** harita. **Sağ:** detay çekmecesi. **Üst bant:** 3 sayaç. **Alt bilgi:** atıflar.
- **Dil:** TR/EN düğmesiyle değişir.
- **Çevrimdışı:** MapLibre dosyaları `web/vendor/` altında yereldir. Çevrimiçi altlık yanıt vermezse (4 sn zaman aşımı) düz arka plan, ilçe sınırı ve hat katmanları gösterilir; alt bilgi bunu belirtir (`docs/ATTRIBUTIONS.md`).
- Senaryo ve Doğrulama sekmeleri yalnızca mock veriyle denendi; gerçek veriyle denemesi [DOĞRULANACAK].

## Dürüstlük notları

- **Kademeler görelidir.** Kritik kademe her zaman yaklaşık %5 çıkar (pilotta 46 / 925 segment; ADR-010, `docs/STATUS.md`, F3-2). Mutlak tehlike düzeyi değildir.
- **Çıktı bir öncelik sıralamasıdır**, kesin hüküm değildir.
- **OSM hatlarının çoğu iletim hattıdır.** 92,4 km hattın 61,0 km'si ≥154 kV (ADR-007). Dağıtım şebekesi için sonuç iddia edilmez. EDAŞ dosyası `data/manual/edas/` altındaysa o kullanılır.
- **Yangın kaynağı bildirildi, tespit edilmedi.** 2025 Menderes, Çeşme ve Ödemiş yangınlarının hat kaynaklı olduğu yalnızca medya ve valilik aktarımında geçiyor; resmî tespit yok (ADR-006, `docs/STATUS.md`, F1-3).
- **Ağaç yüksekliği eski olabilir.** CHM v2 karolarının görüntü tarihleri 2016–2020 arasında karışık; güncel büyüme eksik tahmin edilebilir (ADR-008, `docs/reports/CHM-META.md`).

## Kaynaklar

Veri, yazılım ve görsel atıfları, lisanslar ve bağlantılar: `docs/ATTRIBUTIONS.md`. Copernicus DEM ve CHM v2 atıf metinleri henüz [DOĞRULANMADI] olarak işaretli.
