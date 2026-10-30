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

### F1-4 ham aktarım (DOĞRULANMADI, yalnızca aktarım)

**Yönetmelik:** Elektrik Kuvvetli Akım Tesisleri Yönetmeliği, RG 30.11.2000, sayı 24246. Hükümler Madde 44 fıkra h, i, m, n ve Çizelge-5, 7, 8.

**Resmî kaynak durumu:** mevzuat.gov.tr'den metin alınamadı. Denenen adresler 404 döndü: https://www.mevzuat.gov.tr/MevzuatMetin/7.5.24246.pdf ve https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=24246&MevzuatTur=7&MevzuatTertip=5 (erişim 30.10.2026).

**Kullanılan ikincil kopyalar:**
- Tam metin PDF (tarihsiz, resmî değil): https://www.isguvenligi.net/wp-content/uploads/mevzuat/elektrik_kuvvetli_akim_tesisleri_yonetmeligi.pdf (erişim 30.10.2026). Tablolar metin çıkarımından elle aktarıldı.
- Lexpera (son değişiklik 11.05.2023 yazıyor): https://www.lexpera.com.tr/mevzuat/yonetmelikler/elektrik-kuvvetli-akim-tesisleri-yonetmeligi-2000-24246-11 (erişim 30.10.2026). Çizelge-5, 7 ve 8 ağaç satırları PDF ile eşleşti.
- Resmî Gazete 30.11.2000 sayfası, yalnızca içindekiler (metin kesik): https://www.resmigazete.gov.tr/eskiler/2000/11/20001130.htm

**Madde 44/n (metin):** "İletken çekimini ve hat güvenliğini bozan bütün ağaçlar budanmalı ya da kesilmelidir. Meyve ağaçlarının kesiminden olabildiğince kaçınılmalıdır. Hat iletkenlerinin en büyük salınım konumunda ağaçlara olan en küçük yatay uzaklıkları Çizelge-7'de verilmiştir."

**Madde 44/h (metin):** "İletkenlerin 46 ncı maddeye göre hesaplanan en büyük salgılı durumda üzerinden geçtikleri yer ve cisimlere olan en küçük düşey uzaklıkları Çizelge-8'de verilmiştir."

**Çizelge-7: Ağaçlara en küçük yatay uzaklık (Madde 44/n), m**

| Hattın izin verilen en yüksek sürekli işletme gerilimi (kV) | Yatay uzaklık (m) |
|---|---|
| 0–1 (1 dahil) | 1 |
| 1–170 (170 hariç) | 2,5 |
| 170 | 3,0 |
| 170–420 (420 dahil) | 4,5 |

**Çizelge-8: Hava hattı iletkenlerinin en büyük salgı durumunda üzerinden geçtikleri yerlere en küçük düşey uzaklıklar (Madde 44/h), m**

| Geçilen yer / cisim | 0–1 (1 dahil) | 1–17,5 | 36 | 72,5 | 170 | 420 |
|---|---|---|---|---|---|---|
| Üzerinde trafik olmayan sular | 4,5* | 5 | 5 | 5 | 6 | 8,5 |
| Araç geçmeye elverişli çayır, tarla, otlak vb. | 5* | 6 | 6 | 6 | 7 | 9,5 |
| Araç geçmeye elverişli köy ve şehir içi yolları | 5,5* | 7 | 7 | 7 | 8 | 12 |
| Şehirlerarası karayolları | 7 | 7 | 7 | 7 | 9 | 12 |
| **Ağaçlar** | **1,5** | **2,5** | **2,5** | **3** | **3** | **5** |
| Üzerine herkes tarafından çıkılabilen düz damlı yapılar | 2,5 | 3,5 | 3,5 | 4 | 5 | 8,7 |
| Üzerine herkes tarafından çıkılmayan eğik damlı yapılar | 2 | 3 | 3 | 3,5 | 5 | 8,7 |
| Elektrik hatları | 2 | 2 | 2 | 2 | 2,5 | 4,5 |
| Petrol ve doğal gaz boru hatları | 9 | 9 | 9 | 9 | 9 | 9 |
| Üzerinde trafik olan sular ve kanallar | 4,5 | 4,5 | 5 | 5 | 6 | 9 |
| İletişim (haberleşme) hatları | 1 | 2,5 | 2,5 | 2,5 | 3,5 | 4,5 |
| Elektriksiz demiryolları (ray demirinden ölçülür) | 7 | 7 | 7 | 7 | 8 | 10,5 |
| Otoyollar | 14 | 14 | 14 | 14 | 14 | 14 |

(*) Yalıtılmış hava hattı kablosu kullanıldığında yıldızlı değerler 0,5 m azaltılır. Gerilim sütunları metinde "0-1 (1 dahil), 1-17,5, 36, 72,5, 170, 420" biçimindedir. Ağaç satırında yıldız yoktur.

**Çizelge-5 (karşılaştırma, ağaç değil): Yapılara en küçük yatay uzaklık (Madde 44/i), en büyük salınımda, m**

| Gerilim (kV) | Yatay uzaklık (m) |
|---|---|
| 0–1 (1 dahil) | 1 |
| 1–36 (36 dahil) | 2 |
| 36–72,5 (72,5 dahil) | 3 |
| 72,5–170 (170 dahil) | 4 |
| 170–420 (420 dahil) | 5 |

**Ağaç tanımı ve istisnalar:** Metinde ağaç tanımı görülmedi. Tam metin taraması yapılmadı, yalnızca anahtar kelimelerle bakıldı. Meyve ağaçları için kesimden "olabildiğince kaçınılmalı" ifadesi vardır (44/n).

**Son değişiklik:** Lexpera'ya göre 11.05.2023 (doğrulanmadı). Arama sonuçlarında 2007 (44/o) ve 2018 (46 nci madde notu) değişiklikleri geçiyor; bunların Çizelge-7 ve 8'e etkisi kontrol edilmedi.

**Kapsam dışı:** Çizelge-6 (civardaki tesisler) aktarılmadı; ikincil kopyada bozuk.

### EPDK 2026–2030 ormanlık alan bakım/budama (ham bulgu, DOĞRULANMADI)
- **Kurul kararı numarası, karar tarihi, Resmî Gazete tarihi ve sayısı, madde no:** Bulunamadı. EPDK ve Resmî Gazete sitesinde henüz bakılmadı.
- **BloombergHT** (medya, doğrulanmadı): https://www.bloomberght.com/epdk-dan-elektrik-dagitim-sirketleri-icin-yeni-tarife-donemi-duzenlemesi-3765173 (erişim 30.10.2026). "Ormanlık alanlardaki dağıtım tesislerinin bakım periyotları yıllık hale getirildi"; "orman budama ve temizlik faaliyetleri doğrudan planlı bakım kapsamına alınarak zorunlu tutuldu"; bütçe reel 2,1 kat.
- **24 Saat** (medya, doğrulanmadı): https://www.24saatgazetesi.com/epdkden-elektrik-dagitiminda-bakim-ve-yatirim-duzenlemesi (erişim 30.10.2026). "Bu alanlardaki hatlarda birinci ve ikinci seviye planlı bakım faaliyetleri her yıl gerçekleştirilecek"; 1 Ocak 2026 yürürlük; Resmî Gazete'de yayımlanan kurul kararı. Haber tarihi 17.12.2025; karar tarihi değildir. Bu haberde "budama" kelimesi geçmiyor.
- **Forbes** (medya, doğrulanmadı): https://www.forbes.com.tr/para-yatirim/epdk-2026-2030-elektrik-dagitim-yol-haritasini-belirledi-yatirim-butcesi-1-5-katina-cikti (erişim 30.10.2026). Bütçe 2 kat; ormanlık alan hat bakımını ihmal edene ceza.
- **Çelişki:** Bütçe artışı BloombergHT'de 2,1 kat, Forbes'ta 2 kat.

### İnsan doğrulaması
| Doğrulayan | Tarih | Sonuç | Not |
|---|---|---|---|
| | | | |

Doğrulamadan sonra:
1. risk-modeler config'teki `clearance_band_m` değerlerini günceller ve `placeholder_unverified: false` yapar.
2. Kararı ADR olarak yazar.
