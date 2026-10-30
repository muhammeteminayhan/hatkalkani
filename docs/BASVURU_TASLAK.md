# HatKalkanı — COP31 İklim Teknolojileri Creathonu başvuru taslağı

Taslak sürümü: 30 Eki 2026 (F1B-3 güncellemesi; ilk sürüm F1B-1). Başvuru: 2 Kas 2026 23:59'a kadar, T3 KYS üzerinden (kullanıcı yapar). Son hâl 2 Kas'ta çıkarılacak.

## Nasıl okunur
- **Dil:** Türkçe. Başvuru tek dilde kalır.
- **Sayı türleri:**
  - **Olgu** (#numara): docs/PITCH_FACTS.md maddesine dayanır.
  - **Ürün/takvim parametresi** (PRD, PLAN, config): takımın kendi tasarım kararıdır, dış olgu değildir. Örnek: 100 m parça, 0–100 skor, 3 neden.
  - **[VARSAYIM]:** Senaryo parametresi. Kanıt değildir, aralık olarak sunulur.
  - **[KAYNAK GEREKİYOR]:** Dayanağı henüz yok. Gönderimden önce kaynak bulunur ya da cümle çıkarılır.
  - **[sonuç gelecek]:** Model çıktısı henüz üretilmedi. Rakam uydurulmaz.
- **Dil ilkesi (vakalar):** Elektrik hattı kaynaklı yangın anlatımlarında "bildirildi", "iddia edildi", "aktarıldı" denir. Resmî ya da yargısal tespit olmadığı sürece "tespit edildi" denmez.
- **Form alanları ve sınırlar:** Resmî başvuru formunun alan adlarına ve karakter sınırlarına ulaşılamadı. 30 Eki 2026'da "Creathon" için yapılan aramada resmî sayfa bulunamadı; PITCH_FACTS'te de yok. Bu yüzden her bölüm için önerilen uzunluk yazıldı. **KULLANICIDAN GEREKEN:** T3 KYS formundaki gerçek alan adlarını ve sınırları 1–2 Kas'ta bu taslağın karşısına koy.

---

## 1. Özet (hedef 130–150 kelime; sayım: 145)

HatKalkanı, elektrik dağıtım şirketlerine "budama ve drone ekibini önce nereye göndermeliyim?" sorusunun cevabını verir. Türkiye'de 2025'te 81.473 hektar orman alanı yandı. Hat kaynaklı yangınların payı için resmî veri bulamadık; bir akademisyenin hesabına göre 2021'de yanan alanın yaklaşık dörtte biri enerji nakil hatlarına atfedildi. Yeni tarife döneminde ormanlık alandaki bakım yıllık oldu, budama zorunlu hâle geldi. Şirketin bütçeyi doğru yere harcaması ve bunu belgelemesi gerekiyor. HatKalkanı açık verilerle (OpenStreetMap, ağaç yüksekliği haritası, uydu görüntüsü, rüzgâr, eğim) hatları 100 metrelik parçalara böler ve her parçaya 0–100 arası risk puanı verir. Puanı en çok yükselten üç neden saha ekibine yazılır. Çıktılar: renkli koridor haritası, öncelik sıralı iş emri listesi (CSV, GeoJSON, GeoPackage) ve rüzgârlı günde ilçenin tamamı yerine yalnızca riskli hatları kapsayan kesinti senaryosu. Pilot, İzmir'de bir ilçede yürütülecek. 2025 sezonuyla geriye dönük test planlandı. Sonuçlar abartılmadan, sınırlarıyla raporlanacak. Bu bir karar destek aracıdır; kararı şirketin mühendisi verir.

Dayanak: #1, #7, #21, #25. Parametreler (100 m, 0–100, üç neden): PRD M1.
Sayım yöntemi: boşlukla ayrılmış sözcükler, elle sayıldı (145). Metni değiştirirsen yeniden say.
Gönderimden önce: "dörtte biri" cümlesi yalnızca akademisyen hesabıdır (#25); OGM birincil kaynağı bulunamazsa cümle çıkarılır (Açık noktalar, madde 2).

---

## 2. Problem ve iklimle ilişkisi (öneri: 200–250 kelime)

**Yangın ve iklim.** Türkiye'de 2025'te 3.224 orman yangını çıktı ve 81.473 hektar alan yandı (#21, #1). Yangınlar karbon salar ve karbon tutan ormanı yok eder. Copernicus CAMS'e göre yalnızca Haziran 2025'te Türkiye'nin yangın emisyonu 3,8 milyon ton karbona, yani yaklaşık 13,9 milyon ton CO2'ye ulaştı (#5).

**Hatların payı: resmî veri bulamadık.** Elektrik hatlarının yangınlardaki payına ilişkin rakamlar uzman ve akademisyen aktarımıdır; OGM'nin kendi yayınına ulaşılamadı. Ormancılar Derneği Batı Akdeniz Şubesi'nden bir öğretim üyesi, enerji nakil hatlarından çıkan yangınlarda yanan alanın beşte bire ulaştığını söyledi (2024) (#4). Aynı haberdeki hesaba göre 2021'de yangın sayısının %3,2'si, yanan ormanlık alanın ise yaklaşık dörtte biri (37.358 ha / yaklaşık 140.000 ha) enerji nakil hatlarına atfediliyor (#25). Bu, hat kaynaklı yangınların sayıca az ama büyük olabileceğini düşündürür; kanıt değildir. Etki hesabında yalnızca "yaklaşık beşte bir ile dörtte bir" aralığı, bu uyarıyla kullanılır.

**Vakalar: neden tartışmalı.**
- Diyarbakır–Mardin, 20 Haziran 2024: Yangınlarda kaynaklara göre 11 ile 15 arasında kişi hayatını kaybetti. Yangının elektrik hattından çıktığı iddia edildi; dağıtım şirketi bunu reddetti, bilirkişi raporları çelişiyor (#6).
- İzmir, 2025: Menderes (29 Haziran), Çeşme ve Ödemiş (2 Temmuz) yangınları için valilik açıklamaları ve medyada aktarılan itfaiye raporu iddiaları elektrik hatlarını işaret etti. GDZ Elektrik somut bulgu olmadığını açıkladı. Resmî ya da yargısal bir tespit yok; 15.08.2026 tarihli habere göre Başsavcılık soruşturmaya yer olmadığına karar verdi (#20).
- Bu vakalar hat kaynaklı yangın sayısı olarak sayılmaz ve etki hesabında kullanılmaz. Gösterdikleri tek şey, "hangi hattan çıktı" sorusunun yanıtlanmasının zor olduğu ve önleyici bakım kaydının değer taşıdığıdır.

**Şirketin sorusu cevapsız.** Dağıtım şirketleri budama ve drone denetimi yapıyor. Örneğin SEDAŞ 2026'da 545 km orman koridoru açmayı ve 2.000 ağaç budamayı planlıyor (#14). Ama "ekip bu hafta hangi parçaya önce gitmeli?" sorusunun hat parçası düzeyinde veriyle cevabı eksik.

**İki baskı.**
- **Mevzuat:** Haberlere göre EPDK 2026–2030 döneminde ormanlık alandaki bakım yıllık oldu, budama planlı bakımda zorunlu oldu, aksatana ceza öngörüldü. Planlı bakım bütçesi reel olarak yaklaşık 2,1 katına çıktı (#7). EPDK kararının resmî metni henüz doğrulanmadı.
- **Geniş kesintiler:** Rüzgârlı günlerde ilçe geneli önleyici kesinti yapılıyor. GDZ Elektrik Haziran 2025 sonunda İzmir'de bunu uyguladı (#9). Mersin'de tedbir kesintileri kent merkezini de etkiledi; EMO evde bakıma muhtaç hasta ve yaşlıların mağdur olduğunu söyledi (#10).

---

## 3. Çözüm (öneri: 200–250 kelime)

HatKalkanı bir **karar destek aracıdır**. Hatları 100 m'lik parçalara böler ve her parçaya 0–100 arası risk puanı verir. Puan iki şeyin birleşimidir: tutuşma ihtimali ve yangın çıkarsa yayılma/sonuç ağırlığı.

| Çıktı | Kullanıcı sorusu | Ne verir |
|---|---|---|
| **Koridor risk haritası** | "Hangi hatlar riskli?" | Parçaya tıklayınca puan, puanı en çok yükselten 3 neden ve ham değerler görünür. |
| **İş emri listesi** | "Bu hafta ekibi nereye göndermeliyim?" | Ardışık riskli parçalar açıklığa birleşir, öncelik sırasına dizilir. CSV, GeoJSON, GeoPackage indirilir; her satırda koordinat ve harita linki vardır. |
| **Kesinti senaryosu** | "Yarın rüzgâr güçlü. İlçenin tamamını mı keseyim, yalnızca hangi hatları?" | Tarih ve rüzgâr eşiği seçilir; ilçe geneli ile hedefli kesinti, hat km'si ve etkilenen bina (vekil) olarak karşılaştırılır. |
| **Geriye dönük test** | "Model işe yarıyor mu?" | 2025 yangın sezonu olaylarıyla, güven aralığı ve basit taban çizgileriyle birlikte. [sonuç gelecek] |

**Nasıl hesaplanır.** Faktörler: hatta yakın yüksek ağaç, hatta devrilebilecek ağaç, kuru bitki örtüsü, rüzgâra açıklık, kesintisiz yakıt, yerleşime yakınlık, eğim, geçmiş yangın yoğunluğu. Model kural tabanlıdır ve açıklanabilir; etiketli hat yangını verisi olmadığı için makine öğrenmesi yoktur. Ağırlıklar başlangıç varsayımıdır; pilot şirket verisi ve uzman görüşüyle ayarlanır.

**Ne iddia etmiyoruz.** Liste "kesin budanacak ağaç" bildirmez; **öncelik** verir. Nihai karar şirketin mühendisi ve saha doğrulamasıdır. Yönetmelik mesafeleri henüz resmî metinle doğrulanmadı; modeldeki bant genişlikleri model varsayımıdır, hukuki kural değildir.

---

## 4. Yenilik ve uygulanabilirlik (öneri: 150–200 kelime)

**Yenilik**
- **Hat parçası düzeyi ve gerekçe:** Bakanlığın yapay zekâ destekli yangın risk haritaları bölgesel ölçektedir; enerji nakil hatları dahil 400'den fazla değişken kullanıyor (#15). HatKalkanı bunu tamamlar: şirketin kendi hattında, 100 m çözünürlükte ve "neden" açıklamasıyla.
- **Karar çıktısı:** Risk haritasından öte, doğrudan iş emri ve kesinti senaryosu üretir.
- **Hedefli kesinti:** İlçe geneli yerine yalnızca riskli hatları kesmeyi sayısal olarak karşılaştırır.
- **Dürüst doğrulama:** Başarı iddiası yerine, güven aralıklı geriye dönük test ve açık sınırlar sunulur.

**Dünyada kanıt.** Bitki örtüsü zekâsı alanında Overstory Kasım 2025'te 43 milyon $ B serisi yatırım aldı ve Amerika kıtasındaki en büyük 10 elektrik şirketinin 6'sına hizmet veriyor (#17). Bir ABD iletim şirketi Overstory ile 13 kat yatırım getirisi bildirdi (#18, ikincil kaynak). LiveEO toplam yaklaşık 62,5 milyon $ yatırım aldı (#19, ikincil kaynak). Bu, ihtiyacın başka ülkelerde ödenen bir ihtiyaç olduğunu gösterir; HatKalkanı'nın başarısını göstermez.

**Uygulanabilirlik**
- **Açık veri, ücretsiz başlangıç:** Meta/WRI ağaç yüksekliği haritası 1 m çözünürlükte; ortalama mutlak hatası 2,8 m, ticari kullanım dahil ücretsiz (CC BY 4.0) (#16). Bu hata payı, "ağaç hatta çok yakın mı" kararında belirsizlik yaratır; arayüz bunu gösterecek.
- **Mevcut işi tamamlar:** Enerjisa'nın üç dağıtım şirketinde 141 drone aktif (#13). Drone'ların nereye gideceğini HatKalkanı sıralar; yerine geçmez.
- **Teşvik uyumu:** Aynı tarife döneminde sektörde kullanılan yazılımların yerlileştirilmesi için teşvik getirildi (#8).

---

## 5. Prototip veya kavram kanıtı (öneri: 100–150 kelime)

- **Durum (30 Eki):** Mimari ve ürün tanımı hazır (docs/PRD.md, docs/ARCHITECTURE.md). Veri hattı ve model F2–F3'te kuruluyor. [KULLANICIDAN GEREKEN: 2 Kas itibarıyla gerçek durumu yaz.]
- **Ekran görüntüsü:** [sonuç gelecek: docs/screens/ altında ilk segment haritası. Yoksa bu satırı sil, "prototip zorunlu değil" ilkesiyle kavram kanıtı anlatımıyla gönder.]
- **Pilot:** İzmir'de bir ilçe. İlçe henüz seçilmedi [karar bekliyor: config/aoi.yaml].
- **Çevrimdışı demo:** Tüm akış internetsiz dizüstünde çalışacak şekilde tasarlandı (PRD M6).
- **Geriye dönük test:** 2025 sezonu için planlandı; sonuç yok. Üst %10 ve %20 parçalar için beklenenin kaç katı olay yakalandığı (lift) güven aralığıyla raporlanacak. [sonuç gelecek: docs/reports/ ve data/processed/ altındaki backtest çıktısı]
- **Test verisi sınırı:** Etiketli, resmî olarak hat kaynaklı doğrulanmış yangın kaydı bulunamadı (#20). Bu yüzden test, hat kaynaklı yangınları değil, genel yangın olaylarını (örn. NASA FIRMS) kullanır; sonuçlar buna göre yorumlanır.

---

## 6. İklim etkisi (öneri: 150–250 kelime + tablo)

Ayrıntılı hesap tek yerde: bu bölüm. Sonradan docs/pitch/ETKI_HESABI.md'ye taşınır.

**Ne ölçülür.** HatKalkanı yangını kendisi söndürmez. Etkisi dolaylıdır: bakım önceliğini ve kesinti hedeflemesini iyileştirerek hat kaynaklı yanan alanı azaltmaya çalışır. Bu etki geriye dönük testle **ölçülemez**; test yalnızca sıralamanın olayları ne kadar yakaladığını gösterir. Aşağıdaki tablo bu yüzden tahmin değil, **duyarlılık hesabıdır**: "etkisi şu kadar olursa sonuç şu kadar olur".

**Taban (olgu + uzman hesabı).**
- 2025'te toplam yanan alan: 81.473 ha (#1, #21).
- Hat kaynaklı pay için resmî veri yok. İki uzman/akademisyen aktarımı var: yaklaşık beşte bir (#4) ve 2021 için yaklaşık dörtte bir (#25). Hesapta %20 ile %25 arası kullanılır. İkisi de OGM tarafından doğrulanmış değildir.
- Hesap: 81.473 × 0,20 ≈ 16.300 ha; 81.473 × 0,25 ≈ 20.400 ha; orta nokta (0,225) ≈ 18.300 ha.
- Uyarı: Dörtte bir hesabı 2021 içindir; o yıl yanan ormanlık alan yaklaşık 140.000 ha idi (#25), 2025'te 81.473 ha (#1). Payı 2025'e uygulamak varsayımdır. Gerçek pay daha düşükse tüm sonuçlar aynı oranda küçülür.

**Formül (ulusal ölçekte yıllık, ha/yıl).**
Kaçınılan alan = Taban × Kapsama × Kaçınma payı
Taban = 81.473 ha × hat kaynaklı pay (%20 / %22,5 / %25)

| Senaryo | Taban (ha/yıl) | Kapsama [VARSAYIM] | Kaçınma payı [VARSAYIM] | Kaçınılan yanan alan (ha/yıl) | 2025 toplam yanan alanın payı |
|---|---|---|---|---|---|
| Düşük | ≈ 16.300 | %10 | %1 | ≈ 16 | ≈ %0,02 |
| Orta | ≈ 18.300 | %30 | %3 | ≈ 165 | ≈ %0,2 |
| Yüksek | ≈ 20.400 | %50 | %5 | ≈ 509 | ≈ %0,6 |

(Yuvarlama: ara adımlar yuvarlanmadan hesaplandı; yüksek senaryoda 81.473 × 0,25 × 0,50 × 0,05 ≈ 509.)

- **Kapsama:** Hat kaynaklı yanan alanın, HatKalkanı kullanan şirketlerin ağına düşen payı. Şu an bilinmiyor [KAYNAK GEREKİYOR: pilot ve saha görüşmeleri].
- **Kaçınma payı:** Bu alandaki yangınların, öncelikli bakım ve hedefli kesinti sayesinde çıkmayan ya da küçük kalan payı. Hiçbir ölçüme dayanmıyor; pilotta drone doğrulama oranıyla ve sonraki sezon verisiyle test edilecek.
- **Sınır:** Her hat kaynaklı yangın ağaç temasından çıkmaz; budama hepsini önlemez.
- **Pilot ölçeği:** Tek ilçelik pilotun etkisi bu ulusal tablonun çok altındadır; tablo, ölçeklenirse ne olabileceğini gösterir.

**CO2e'ye çevirme.**
Kaçınılan emisyon (t CO2e/yıl) = Kaçınılan alan (ha/yıl) × f (t CO2e/ha)
- **f:** [KAYNAK GEREKİYOR] Hektar başına emisyon katsayısı için birincil kaynak bulunamadı (#23). Aday kaynaklar: EMEP/EEA Guidebook 11.B, IPCC 2006 Cilt 4 Bölüm 2 ve Türkiye'nin UNFCCC ulusal envanter raporu (CRF); hiçbiri henüz okunmadı. Katsayı gelmeden CO2e rakamı yazılmaz. Yazılacağında ormanın türüne göre aralık verilecek.
- **Ölçek bağlamı:** Yalnızca Haziran 2025'te Türkiye'nin yangın emisyonu yaklaşık 13,9 Mt CO2'dir (#5). Bu tek ay, katsayı değildir.

**Kesinti senaryosu etkisi (pilot ilçe, tarih seçilince).** Bu sosyal etkidir, iklim etkisi değildir; ayrı verilir.
- Kaçınılan kesinti = ilçe geneli hat km'si − hedefli hat km'si (hat-km)
- Etkilenmeyen bina (vekil) sayısı
- Kapsanan risk oranı
- Değerler: [sonuç gelecek: scenario_<tarih>.json]. Bina sayısı OSM/Overture'den bir vekildir, abone sayısı değildir.

**Pilotta ölçülecek göstergeler.** Listedeki parçaların drone ile doğrulanma oranı (PRD pilot ölçütü); sahada bulunan kritik nokta sayısı; ekip planlama süresi. [sonuç gelecek]

---

## 7. İş modeli (öneri: 150–200 kelime)

**Müşteri.** Elektrik dağıtım şirketleri (EDAŞ). İkincil: OGM bölge müdürlükleri, sigorta ve risk ekipleri.

**Neden şimdi.** Haberlere göre ormanlık alandaki bakım yıllık ve zorunlu oldu, aksatana ceza öngörüldü; planlı bakım bütçesi reel olarak yaklaşık 2,1 katına çıktı (#7). GDZ Elektrik 2026–2030 için 64,2 milyar TL yatırım planlıyor ve ormanlık alan hatlarındaki yangın tehlikesini vurguluyor (#12). Bu toplam yatırım planıdır, HatKalkanı'na ayrılan pay değildir. Şirketin bütçeyi doğru yere harcaması ve bunu belgelemesi gerekiyor. HatKalkanı'nın iş emri listesi ve kayıtları bu belgelemeye yardım eder.

**Gelir akışları (taslak).**
1. Hat-km başına yıllık abonelik.
2. Sezon öncesi risk raporu.
3. Ek ücretli kesinti modülü.

**Fiyat.** [KAYNAK GEREKİYOR: fiyat henüz yok. Saha görüşmelerinden ve pilot sonrası belirlenir.]

**Pilot.** 3 aylık ücretsiz pilot, 300 km orman içi hat (PRD ürün planı). Başarı ölçütü: listedeki parçaların drone ile doğrulanma oranı.

**Büyüme.** İletim şebekesi, demiryolu, sigorta, Akdeniz ülkeleri.

**Veri riski.** Gerçek şebeke topolojisi ve fider verisi şirketten gelir; ilk sürüm OSM hatlarıyla çalışır. OSM hatları gerçek şebekeyle birebir olmayabilir; pilotta şirket verisiyle düzeltilir.

---

## 8. Ekip (öneri: 100–150 kelime)

Üye bilgileri, rol ve yetkinlik tablosu: **docs/pitch/EKIP.md**. Başvuruya oradan kopyalanır.

[KULLANICIDAN GEREKEN: ad, rol, yetkinlik kanıtı, danışman. Doldurulmadan bu bölüm gönderilmez.]

Eklenecek cümle iskeleti (bilgiler gelince):
- "Ekibimizde [rol: CBS/veri], [rol: model], [rol: arayüz/ürün] ve [rol: sektör bağlantısı] var."
- "Mevzuat varsayımlarını [danışman adı, elektrik mühendisi] resmî metinle doğrulayacak."
- "Final haftasında en az 3 kurumla görüşüp en az bir geri bildirimi ürüne yansıtacağız."

---

## 9. Yol haritası (öneri: tablo)

| Zaman | Adım | Çıkış |
|---|---|---|
| 2 Kas | Başvuru | Bu taslak |
| 6 Kas | Finalist duyurusu | — |
| 9–13 Kas | Mentorluk | Model ve arayüz cilası; geriye dönük test sonuçlarının dürüst özeti |
| 15–16 Kas | Antalya'da 24 saatlik final | Çevrimdışı demo; 5 dk sunum + 3 dk soru |
| Final sırasında | En az 3 kurumla saha görüşmesi (EDAŞ, OGM/Tarım ve Orman, sigorta veya enerji yatırımcısı) | En az bir geri bildirim ürüne yansır |
| Final sonrası | Mevzuat bantlarının uzman doğrulaması; 1 EDAŞ ile 3 aylık pilot | Pilot şirket verisiyle ağırlık ayarı; drone doğrulama oranı |
| Sonraki | ML (etiketli veri gelirse), gerçek zamanlı rüzgâr, drone görüntü işleme, iletim şebekesi | v0.1 kapsamında değil |

Not: 6 Kas'ta finalist olunamazsa F4'ten sonrası takımın kararıyla sürer (PLAN). Final sonrası için tarih verilmedi; EDAŞ kabulü olmadan takvim sözü vermiyoruz.

---

## 10. Kaynaklar ve atıflar

Kaynağın tam listesi docs/ATTRIBUTIONS.md. Başvuruya kısa hâli konur. Şartname verinin, yazılımın ve üçüncü taraf içeriğin kaynağını istiyor.

**Veri**
- OpenStreetMap (ODbL 1.0): © OpenStreetMap contributors
- Meta & WRI Canopy Height Maps (CC BY 4.0)
- Sentinel-2 L2A (Copernicus açık veri)
- Copernicus DEM GLO-30 [atıf metni eklenecek]
- ESA WorldCover 2021 (CC BY 4.0)
- Overture Maps (binalar) [atıf metni eklenecek]
- Open-Meteo (CC BY 4.0)
- NASA FIRMS [atıf metni eklenecek]

**Yazılım.** MapLibre GL JS (BSD-3-Clause); Python kütüphaneleri (listesi F5'te lisanslarıyla eklenecek).

**Yapay zekâ.** Kod, analiz ve metin üretiminde Claude Code (Anthropic) kullanıldı. İçeriğin doğruluğunu takım kontrol etti ve sorumluluğunu taşır. [KULLANICIDAN GEREKEN: göndermeden önce metindeki her olguyu kendin kontrol et, sonra bu cümleyi onayla.]

**Olgu kaynakları (PITCH_FACTS).** Metinde kullanılan: #1, #4–#10, #12–#21, #25. Hesap: #1 ile #4 ve #25'in çarpımı (bölüm 6). Boşluk: #23. Metinde kullanılmayanlar: #2, #3, #24 (doğrulanamadı ya da düzeltme gerektiriyor), #11. Bağlantılar PITCH_FACTS.md'de.

---

## Açık noktalar (2 Kas'ta kapatılacak)

| # | Açık nokta | Sahibi |
|---|---|---|
| 1 | T3 KYS formunun alan adları ve karakter sınırları | Kullanıcı |
| 2 | #1, #4 ve #25 için birincil kaynak (OGM / Tarım ve Orman): toplam yanan alan ve hat kaynaklı pay. Bulunamazsa özetteki "dörtte biri" cümlesi, bölüm 2'deki pay cümleleri ve bölüm 6 tabanı "uzman hesabı" etiketiyle kalır ya da çıkarılır | data-scout / kullanıcı |
| 3 | İzmir vakaları (#20): İzmir Büyükşehir İtfaiye raporlarının asıl metni (bilgi edinme başvurusu) gelene kadar "iddia edildi / bildirildi" dili korunur | data-scout / kullanıcı |
| 4 | Ekip, danışman bilgileri (EKIP.md) | Kullanıcı |
| 5 | Pilot ilçe adı (K1) | Kullanıcı |
| 6 | Prototip durumu ve ekran görüntüsü | Kullanıcı / qa-tester |
| 7 | CO2e katsayısı f (#23) için birincil kaynak: UNFCCC Türkiye NIR (CRF) ve IPCC 2006 Cilt 4 Bölüm 2 | data-scout / pitch-writer, 2 Kas turu |
| 8 | Etki tablosundaki kapsama ve kaçınma payı varsayımlarının ekip/mentor onayı | Kullanıcı |
| 9 | Geriye dönük test sonucu geldiyse (F3) bölüm 5'e dürüstçe eklenmesi. Gelmediyse "planlandı" kalır | pitch-writer |
| 10 | Yönetmelik mesafeleri DOĞRULANDI olmadan kesin kural gibi yazılmaz; EPDK kararının resmî metni (#7) doğrulanmadı | Danışman (elektrik mühendisi) |
| 11 | Yapay zekâ kullanım beyanının onayı | Kullanıcı |

---

## Değişiklik notu (30 Eki)

Neden: F1B-2 PITCH_FACTS'te hatalı sayıları düzeltti; F1-3 vaka raporu İzmir ve Diyarbakır vakalarının resmî olarak doğrulanmadığını gösterdi.

**Çıkarılan sayılar**
- Hat kaynaklı yangınların sayı payına ilişkin yüzde rakamı (özet ve bölüm 2): #2'deki bu rakam hatların payı değil, uzmanın "kaza" kategorisi payıdır (#24). Metinden çıktı. Yerine #25'teki 2021 sayı payı (%3,2), akademisyen hesabı olarak geldi.
- Bu rakamdan türetilen yangın sayısı hesabı (PITCH_FACTS'te 22. madde): hesap geçersiz; metinde ve kaynak listesinde yok.
- "Beşte biri ile dörtte biri" ifadesi özetten çıktı; yerine yalnızca #25'e dayanan "2021, yaklaşık dörtte bir, akademisyen hesabı" cümlesi kondu.
- #3 (hat kaynaklı payın 2020 ve 2023 değerleri) doğrulanamadığı için bölüm 2'den çıkarıldı. Birincil kaynak bulunursa yeniden eklenebilir.

**Değiştirilen sayılar ve ifadeler**
- Bölüm 6 tabanı: "~%25 (#2)" yerine "dörtte bir (#25, 2021, akademisyen hesabı)". Aralık %20–%25 kaldı (#4, #25). Hektar değerleri (≈ 16.300 / 18.300 / 20.400) doğrudan #1 × pay olarak yeniden hesaplandı, değerler aynı.
- Yüksek senaryo ≈ 510 ha yerine ≈ 509 ha (yuvarlanmamış ara adımlarla). Düşük ≈ 16 ve orta ≈ 165 ha değişmedi. Her satıra 2025 toplam yanan alana oranı eklendi (≈ %0,02 / %0,2 / %0,6).
- Bölüm 2 Diyarbakır–Mardin: "15 kişi yaşamını yitirdi, tesisler gündeme geldi" yerine "11 ile 15 arası, hattan çıktığı iddia edildi, şirket reddetti, bilirkişi raporları çelişiyor" (#6 düzeltmesi).
- Bölüm 2 İzmir (#20): "itfaiye raporlarıyla bildirildi" yerine "valilik açıklamaları ve medyada aktarılan itfaiye raporu iddiaları; resmî ya da yargısal tespit yok; Başsavcılık soruşturmaya yer olmadığına karar verdi (15.08.2026 haberi)". Çeşme için itfaiye raporu ifadesi kullanılmadı.
- #7 (mevzuat) "haberlere göre" olarak etiketlendi; EPDK kararının resmî metni doğrulanmadı.
- Özet: 140 yerine 145 kelime (elle sayım).
- Bölüm 5'e "test verisi sınırı" maddesi eklendi: hat kaynaklı doğrulanmış yangın kaydı yok.

**Etiketle bırakılanlar**
- CO2e katsayısı f (#23): [KAYNAK GEREKİYOR]; CO2e rakamı yazılmadı. Aday listesinden, PITCH_FACTS'te geçersiz bulunan "Zafer vd. 2019" çıkarıldı.
- Kapsama ve kaçınma payı: [VARSAYIM] ve [KAYNAK GEREKİYOR].
- Pilot ilçe: yer tutucu kaldı.
