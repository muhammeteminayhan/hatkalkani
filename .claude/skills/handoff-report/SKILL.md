---
name: handoff-report
description: Alt ajanların işi bitirince orkestratöre döndüreceği kısa teslim raporunun biçimi. Tüm alt ajanlara önceden yüklenir.
user-invocable: false
---

# Teslim raporu biçimi

İşin bitince orkestratöre YALNIZCA aşağıdaki raporu döndür (en fazla 200 kelime).

Rapora ayrıntı, uzun tablo, log veya kod parçası koyma. Gerekirse bunları `docs/reports/<görev-id>-<kısa-ad>.md` dosyasına yaz ve yolunu ver.

~~~
GÖREV: <görev-id> — <bir satır>
DURUM: ✅ tamam | ⚠️ kısmen | ❌ başarısız
YAPILANLAR:
- 2–5 madde
DEĞİŞEN DOSYALAR: yol listesi (en fazla 10; fazlası için klasör adı)
DOĞRULAMA: çalıştırılan komut → sonuç (ör. `uv run pytest tests/ingest -q` → 12 passed)
VARSAYIMLAR / RİSKLER: 1–3 madde veya "yok"
KULLANICIDAN GEREKEN: "yok" veya ne, neden, nereye konacak
SONRAKİ ÖNERİ: 1–2 madde
AYRINTI: docs/reports/... (varsa)
~~~

## Kurallar
- **Doğrulanmamış iş:** Doğrulamadığın bir şeyi "tamam" diye raporlama. Test çalıştıramadıysan DURUM ⚠️ olsun.
- **Kapsam:** Görevin dışına çıkma. Kapsam dışı bir sorun gördüysen SONRAKİ ÖNERİ'ye yaz.
- **Başka ajanın dosyası:** Başka bir ajanın dosyasını değiştirmen gerekiyorsa değiştirme; raporda belirt.
