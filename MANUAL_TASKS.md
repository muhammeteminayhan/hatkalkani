# Kullanıcıya ait işler

Bu dosyada Claude'un yapamadığı veya yapmaması gereken işler var. Orkestratör yeni iş çıktıkça buraya ekler.

Durum: ⬜ bekliyor · ✅ tamam

## 🔴 Öncelikli: FIRMS anahtarı ve ilk commit
30 Eki (F0-4 ve orkestratör kontrolü, değer okunmadan): `.env` içindeki FIRMS_MAP_KEY dolu ve gerçek anahtar biçiminde (32 hex). Aynı değer `.env.example` şablonunda da vardı ve yerel ilk commit'e girdi. Şablondaki değer silindi ve ilk commit onayınızla anahtarsız yeniden yazıldı (c423a81); uzak depo yok, push yapılmadı. Ajanların `.env`'e erişimi izin kuralıyla engelli; anahtarın geçerliliği F2-5'te betikle sınanacak. İsterseniz şimdi kendiniz de bakabilirsiniz: tarayıcıda `https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY=ANAHTARINIZ` (anahtarı sohbete yazmayın).

| # | İş | Neden | Nasıl | Son tarih | Durum |
|---|---|---|---|---|---|
| 4 | NASA FIRMS MAP_KEY alın | 2015–2025 yangın noktaları (geriye dönük test) için gerekir; kayıt e-posta doğrulaması ister | https://firms.modaps.eosdis.nasa.gov/api/map_key/ → ücretsiz anahtar | 31 Eki (F1-2 erişim testi, F2-5 indirme) | ✅ |
| 5 | `.env` dosyasını oluşturun | Anahtar Claude'a gösterilmeden betiklerce kullanılır | `.env.example` dosyasını `.env` adıyla kopyalayın; `FIRMS_MAP_KEY=` satırına anahtarı yazın. Anahtarı sohbete yapıştırmayın | 31 Eki | ✅ |
| 4a | İlk commit'i düzeltme onayı verin | Anahtar git geçmişinde kalırsa ileride bir push ile sızar | Orkestratör soracak: `git commit --amend` ile tek commit'lik geçmiş, şablonu temizlenmiş hâliyle yeniden yazılır (uzak depo yok) | Faz 1 commit'inden önce | ✅ (30 Eki, c423a81) |
| 4b | (İsteğe bağlı) FIRMS anahtarını yenileyin | Değer şablon dosyasında durduğu için bir ajanın bağlamına girmiş olabilir; makine dışına gönderilmedi. Risk düşük | FIRMS MAP_KEY sayfasından yeni anahtar isteyip `.env`'e yazın | 3 Kas (F2-5 öncesi) | ⬜ |

## Başlamadan önce (bugün, ~30 dk)
| # | İş | Neden | Nasıl | Durum |
|---|---|---|---|---|
| 1 | Claude masaüstü uygulamasını güncelleyin | Opus 5.5, Sonnet 5.5 ve Haiku 5.5 yeni bir Claude Code sürümü ister (Haiku 5.5 için v2.1.293+) | macOS: Claude → Check for Updates · Windows: Help → Check for Updates | ✅ (Haiku 5.5 ajanları çalışıyor) |
| 2 | (Yalnız Windows) Git for Windows kurun | Code sekmesi Windows'ta Git olmadan açılmaz | git-scm.com/downloads/win → kurun → uygulamayı yeniden başlatın | ✅ (git 2.51.1) |
| 3 | Node.js LTS kurun (önerilir) | Arayüz testi ve ekran görüntüsü için Playwright MCP gerekir | nodejs.org → LTS → uygulamayı yeniden başlatın | ✅ (node 24.13.0) |
| 6 | En az 10 GB boş disk ayırın | Python ortamı ve kırpılmış veri önbelleği | — | ✅ (111 GB boş) |
| 7 | Klasörü Claude Code'da açın | Proje ajanları, ayarlar ve CLAUDE.md yalnızca proje kökünden yüklenir | Claude masaüstü → Code sekmesi → ortam: **Local** → **`Desktop\hatkalkani`** (proje kökü; `.claude/` bunun içinde). Güven (trust) sorusu gelirse onaylayın; alt ajanların MCP sunucuları buna bağlı. *30 Eki: kullanıcı iç içe klasörü düzleştirdi; oturum proje köküne taşındı.* | ✅ |
| 8 | Ana oturumu ayarlayın | Ana oturum Opus 5.5 + max olmalı | Model menüsünde Opus 5.5 seçili olsun (proje ayarı zaten bunu seçer). Prompt kutusuna `/effort max` yazın. max yalnızca o oturum için geçerlidir; her yeni ana oturumda tekrarlayın | ✅ (30 Eki: Opus 5.5 · max) |

## Proje sırasında
| # | İş | Neden | Nasıl | Son tarih |
|---|---|---|---|---|
| 9 | K1: pilot ilçeyi seçin | — | Orkestratör seçenekli soracak | 31 Eki |
| 10 | Takım bilgilerini yazın | Başvuru ve sunum | docs/pitch/EKIP.md: ad, rol, yetkinlik, danışman (şablon hazır) | 1 Kas |
| 10a | Başvuru formunun alanlarını iletin | Taslak resmî alan adlarına ve karakter sınırlarına göre uyarlanacak; pitch-writer resmî sayfayı bulamadı | T3 KYS formundaki alan adlarını ve sınırlarını docs/pitch/FORM_ALANLARI.md'ye yazın ya da formun ekran görüntüsünü docs/pitch/ altına koyun | 1 Kas |
| 10b | Başvuru taslağını gözden geçirin | [VARSAYIM] etiketli etki varsayımları, yapay zekâ beyanı ve "insan doğrulaması" notlu cümleler onayınızı ister | docs/BASVURU_TASLAK.md'yi okuyun; onaylamadıklarınızı not edin. Taslak 30 Eki'de düzeltildi (F1B-3). Özellikle şu varsayımlara bakın: kapsama %10 / %30 / %50, kaçınma %1 / %3 / %5 ve 2021 için verilen %20–25 hat payının 2025'e uygulanması | 1 Kas |
| 11 | Başvuruyu gönderin | Yalnızca takım yapabilir | T3 KYS: takım + danışman + dil; metin docs/BASVURU_TASLAK.md'de | **2 Kas 23:59** |
| 12 | Yönetmelik mesafelerini doğrulayın | Hukuki ve teknik iddia, insan onayı ister | data-scout'un docs/REGULATION_NOTES.md'ye aktardığı tabloyu resmi metinle karşılaştırın; doğruysa "DOĞRULANDI" yazın. Ekipte elektrik mühendisi yoksa danışmana sorun. *30 Eki (F1-4): ajan resmî metne erişemedi (mevzuat.gov.tr 404); Çizelge-7 ve 8 iki ikincil kopyadan aktarıldı. EPDK 2026–2030 bakım/budama kararının künyesi (karar no, tarih, Resmî Gazete) de bulunamadı; EPDK sitesinden bakılması gerekiyor* | 3 Kas |
| 13 | K2: risk sonuçlarını gözden geçirin | — | — | ~6 Kas |
| 14 | K3: demoyu kendiniz deneyin | — | — | ~10 Kas |

## İsteğe bağlı (değeri yüksek)
| # | İş | Neden | Nasıl |
|---|---|---|---|
| 15 | Bir EDAŞ'tan örnek hat verisi isteyin | OSM'de orta gerilim hatları eksik olabilir; pilot için en güçlü kanıt | Görüşmelerde isteyin; gelirse data/manual/edas/ altına koyun |
| 16 | EFFIS yanmış alan poligonlarını isteyin | Vaka incelemesi | EFFIS veri talep formu |
| 17 | OGM'den il bazında yangın nedeni istatistiği isteyin | Hat kaynaklı yangın konumları | Bilgi edinme başvurusu (final öncesi gelmeyebilir) |
| 17a | İzmir BB İtfaiyesi'nden 2025 yangın raporlarını isteyin | F1-3: Menderes, Çeşme ve Ödemiş'te hat kaynaklı olduğu yalnız basında geçiyor; birincil rapor bulunamadı | Bilgi edinme / CİMER başvurusu: 29.06.2025 Menderes, 02.07.2025 Çeşme ve Ödemiş yangınları için yangın nedeni raporu (final öncesi gelmeyebilir) |

## Final
| # | İş | Ne zaman | Nasıl |
|---|---|---|---|
| 18 | "Final başladı" deyin | 15 Kas 13:00 | Orkestratör `final-start` etiketini atar |
| 19 | Saha görüşmelerini yapın (en az 3 kurum) | 15–16 Kas | docs/SAHA_GORUSMELERI.md şablonuyla kaydedin |

## Notlar
- Opus 5.5 max yoğun kullanımda plan limitlerini hızlı tüketir; `/usage` ile izleyin.
- `CLAUDE_CODE_EFFORT_LEVEL` ortam değişkenini ayarlamayın. Bu değişken alt ajanların kendi effort ayarlarını ezer ve hepsini max'a zorlar.
