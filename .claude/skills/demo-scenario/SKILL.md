---
name: demo-scenario
description: HatKalkanı'nın 90 saniyelik demo akışı ve arayüz kabul kriterleri. Arayüz geliştiren veya test eden alt ajanlara önceden yüklenir.
user-invocable: false
---

# Demo akışı (90 saniye, 5 dakikalık sunumun içinde)

Hedef izleyici: jüri ve bir EDAŞ bakım mühendisi. Her adım tek tıklamayla olmalı.

1. **Açılış (10 sn):** Harita pilot ilçede açılır. Hatlar risk kademesine göre renklidir. Üst bantta API'den gelen üç sayaç vardır:
   - hat km'si,
   - "kritik" parça sayısı,
   - bu haftanın iş paketi sayısı.
2. **İş listesi (20 sn):** Sol panelde sıralı iş paketleri listelenir. İlk satıra tıklayınca harita oraya yakınlaşır. Detay panelinde şunlar görünür:
   - skor ve kademe,
   - en çok katkı veren 3 neden (Türkçe),
   - ham değerler (kanopi, NDMI, eğim, yakın bina sayısı),
   - koordinat ve "Haritada aç" bağlantısı.
3. **Dışa aktarım (10 sn):** "CSV indir" ve "GeoPackage indir" düğmeleri çalışır; dosya iner.
4. **Senaryo (30 sn):**
   - "Senaryo" sekmesinde önceden hesaplanmış rüzgârlı gün seçilir (config `demo` alanı; 2025 Haziran sonu İzmir).
   - Rüzgâr eşiği kaydırıcısı vardır.
   - Kesinti adayı hatlar vurgulanır.
   - Karşılaştırma kartında ilçe geneli ve HatKalkanı yan yana gösterilir: kesilen hat km'si, etkilenen bina (vekil) ve kapsanan risk oranı.
   - "Vekil ölçüm" notu görünür.
5. **Doğrulama (20 sn):** "Doğrulama" sekmesi şunları gösterir:
   - 2025 sezonu yangın noktaları haritada,
   - üst %10 ve %20 parçaların yakaladığı olay payı ile beklenen pay, güven aralığıyla,
   - taban çizgileri,
   - sınırlar notu.

# Kabul kriterleri
- **Hız:** Yerel sunucudan ilk açılış 3 saniyenin altındadır. Etkileşimler akıcıdır.
- **Çevrimdışı:** İnternet yokken tüm akış çalışır: MapLibre yerel kopyası ve yerel yedek altlık.
- **Projeksiyon:** 1920×1080'de yazılar okunur, kontrast yüksektir. Renk tek bilgi taşıyıcısı değildir; kademe adı da yazar.
- **Dil:** Varsayılan Türkçe, tek tıkla İngilizce.
- **Sayılar:** Ekrandaki tüm sayılar API'den gelir; sabit sayı yoktur.
- **Atıflar:** Veri atıfları altbilgide görünür.
- **Konsol:** Tarayıcı konsolunda hata yoktur.
- **Ekran görüntüleri:** Her adımın görüntüsü `docs/screens/` altında durur (sunum için).
