# Ürün tanımı — HatKalkanı v0.1 (Creathon MVP)

## Problem
- **Yanan alan:** Türkiye'de 2025'te 81.473 ha alan yandı. Elektrik hatları yangınların yaklaşık %7'sine ama yanan alanın yaklaşık %25'ine karşılık geliyor (docs/PITCH_FACTS.md).
- **Önceliklendirme eksik:** Dağıtım şirketleri drone denetimi ve koridor budaması yapıyor, ama "ekip önce nereye gitmeli" sorusu hat parçası düzeyinde veriyle yanıtlanmıyor.
- **Geniş kesintiler:** Rüzgârlı günlerde ilçe veya köy genelinde önleyici kesinti yapılıyor (İzmir 2025). Mersin'deki tedbir kesintileri kent merkezini de etkilediği için eleştirildi.
- **Mevzuat baskısı:** EPDK 2026–2030 döneminde ormanlık alandaki bakım yıllık, budama zorunlu oldu ve aksatana ceza öngörüldü. Şirketin bütçeyi doğru yere harcaması ve bunu belgelemesi gerekiyor.

## Kullanıcılar
- **Birincil:** EDAŞ bakım planlama mühendisi (haftalık budama ve drone planı).
- **İkincil:**
  - EDAŞ işletme ve kriz masası (rüzgârlı günde kesinti kararı),
  - OGM bölge müdürlüğü (koordinasyon),
  - sigorta ve risk ekipleri.

## Kullanıcının soruları
1. "Bu hafta budama ekiplerimi hangi 40 hat parçasına göndermeliyim?"
2. "Bu parça neden riskli? Ekibe ne söyleyeyim?"
3. "Yarın rüzgâr 60 km/s. İlçenin tamamını mı kesmeliyim, yoksa yalnızca hangi hatları?"
4. "Modelin işe yaradığını nasıl bilebilirim?"

## MVP özellikleri ve kabul kriterleri
| # | Özellik | Kabul kriteri |
|---|---|---|
| M1 | Koridor risk haritası | Pilot ilçedeki tüm havai hatlar 100 m'lik parçalar halinde renkli. Bir parçaya tıklanınca skor, 3 neden ve ham değerler görünür. |
| M2 | İş emri listesi | Ardışık riskli parçalar açıklıklara birleşir ve sıralanır. CSV, GeoJSON ve GPKG indirilebilir. Her satırda koordinat ve harita linki vardır. |
| M3 | Kesinti senaryosu | Tarih ve rüzgâr eşiği seçilince hedefli kesinti ile ilçe geneli karşılaştırılır: hat km'si, etkilenen bina (vekil), kapsanan risk oranı. |
| M4 | Geriye dönük test | 2025 sezonu olaylarıyla üst %10 ve %20 lift değeri, güven aralığı ve taban çizgileri verilir. Sınırlar açıkça yazılır. |
| M5 | Kaynaklar | Arayüzde veri atıfları görünür; docs/ATTRIBUTIONS.md eksiksizdir. |
| M6 | Çevrimdışı demo | İnternet olmadan dizüstünde açılır ve tüm akış çalışır. |

## Kapsam dışı (v0.1)
- gerçek zamanlı sensör,
- drone görüntü işleme,
- gerçek şebeke topolojisi ve fider verisi,
- mobil uygulama,
- kullanıcı hesapları,
- ML eğitimi (etiketli veri yok).

## Başarı ölçütleri (demo)
- **Geriye dönük test:** Üst %20 parçanın yakaladığı hat yakını olay payı ve bunun beklenen paya oranı (lift), güven aralığıyla raporlanır. Sonuç ne çıkarsa dürüstçe yazılır.
- **Kesinti senaryosu:** Hedefli kesintide kesilen hat km'si ve etkilenen bina (vekil), ilçe geneli kesintiyle karşılaştırılır.
- **Demo akışı:** 90 saniyede kesintisiz tamamlanır.

## İş modeli taslağı
pitch-writer bu taslağı geliştirir.
- **Gelir:**
  - hat-km başına yıllık abonelik,
  - sezon öncesi risk raporu,
  - ek ücretli kesinti modülü.
- **Pilot:** 300 km orman içi hatta 3 aylık ücretsiz pilot. Başarı ölçütü, listedeki parçaların drone ile doğrulanma oranı.
- **Büyüme:** iletim şebekesi, demiryolu, sigorta, Akdeniz ülkeleri.
