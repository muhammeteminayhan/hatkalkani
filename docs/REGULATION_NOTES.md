# Mevzuat notları

Bu dosya hukuki/teknik iddia içerir. Değerler, ekipten bir elektrik mühendisi veya danışman resmi metinle karşılaştırıp **DOĞRULANDI** yazmadan kesin kural gibi kullanılmaz. Doğrulanana kadar config/risk_weights.yaml'daki bant genişlikleri model varsayımıdır.

## 1. EPDK 2026–2030 tarife dönemi (doğrulanmış haber kaynakları)
- **Bakım:** Ormanlık alandaki dağıtım tesislerinin bakım periyodu yıllık hale getirildi.
- **Budama:** Orman budama ve temizlik faaliyetleri planlı bakım kapsamına alındı ve zorunlu oldu.
- **Yaptırım:** Planlı bakımı, özellikle orman alanlarındaki hat bakımını aksatan şirketlere idari yaptırım öngörüldü.
- **Bütçe:** Planlı bakım bütçesi reel olarak ~2,1 katına çıktı.
- **Kaynaklar:** PITCH_FACTS #7 (Bloomberg HT, Ekonomi Gazetesi).
- **Yapılacak:** EPDK'nın ilgili kurul kararının veya usul ve esasların resmi metnini bul ve madde numarasını ekle (data-scout, F1-4).

## 2. Elektrik Kuvvetli Akım Tesisleri Yönetmeliği
- **Künye:** Resmî Gazete 30.11.2000, sayı 24246; sonraki değişiklikler dahil (ör. RG 23.01.2018/30310).
- **İlgili hüküm (ikincil kaynakta aktarılan):** İletken çekimini ve hat güvenliğini bozan bütün ağaçlar budanmalı ya da kesilmelidir. Yönetmelikte, hat iletkenlerinin en büyük salınım konumunda ağaçlara olan en küçük yatay uzaklıklar için bir tablo bulunur.
- **İkincil kaynak:** İTÜ ders notu, https://web.itu.edu.tr/kalenderli/50Hz_Elektrik_Manyetik_Alanlar_Kalenderli.pdf
- **Yapılacak:** Resmi metni mevzuat.gov.tr'den bul. Ağaçlarla ilgili yatay ve düşey uzaklık tablolarını aşağıya aktar (F1-4).

### Ham bulgular (data-scout doldurur — DOĞRULANMADI)
| Gerilim sınıfı | Ağaca en küçük yatay uzaklık (m) | Ağaca en küçük düşey uzaklık (m) | Madde/Çizelge | Kaynak URL | Durum |
|---|---|---|---|---|---|
| AG (≤1 kV) | ? | ? | ? | ? | DOĞRULANMADI |
| OG (1–36 kV) | ? | ? | ? | ? | DOĞRULANMADI |
| YG (>36 kV) | ? | ? | ? | ? | DOĞRULANMADI |

### İnsan doğrulaması
| Doğrulayan | Tarih | Sonuç | Not |
|---|---|---|---|
| | | | |

Doğrulamadan sonra:
1. risk-modeler config'teki `clearance_band_m` değerlerini günceller ve `placeholder_unverified: false` yapar.
2. Kararı ADR olarak yazar.
