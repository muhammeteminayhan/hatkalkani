# İlk prompt

## Yapıştırmadan önce
1. MANUAL_TASKS.md → "Başlamadan önce" adımlarını tamamlayın (en az 1, 2, 5, 7 ve 8).
2. Claude masaüstünde Code → Local → bu klasörü açın. Model Opus 5.5 olsun; prompt kutusuna `/effort max` yazın.
3. Aşağıdaki metni olduğu gibi yapıştırın.

---

```text
HatKalkanı projesine başlıyoruz. Bu oturum projenin ana oturumu ve sen orkestratörsün: işi planla, alt ajanlara dağıt, sonuçlarını denetle ve karar ver. Kod yazma, veri indirme, test çalıştırma ve uzun dosya okuma işlerini CLAUDE.md'deki yönlendirme tablosuna göre alt ajanlara ver. Kendi bağlamını temiz tut.

Önce docs/PLAN.md, docs/STATUS.md ve MANUAL_TASKS.md dosyalarını oku. Diğer dokümanları gerektiğinde alt ajanlara okut.

Bu oturumun hedefi:
- Faz 0'ı (kurulum denetimi) tamamla.
- Faz 1'i (veri keşfi) başlat: F1-1, F1-2, F1-3 ve F1-4 data-scout görevlerini paralel çalıştır.
- F1B'yi (başvuru taslağı) pitch-writer ile arka planda başlat. Başvurunun son tarihi 2 Kasım 23:59; taslak 1 Kasım akşamına hazır olsun.
- K1 kontrol noktasında DUR. Aday ilçeleri karşılaştırma tablosuyla göster, bir öneri yap ve seçimi bana seçenekli sor. Onayım olmadan Faz 2'ye geçme.

Faz 0'da ayrıca:
1. .claude/agents altındaki 10 ajanın ve .claude/skills altındaki 6 skill'in yüklendiğini doğrula. Frontmatter hatası varsa düzelt ve bana bildir.
2. Ajanlara satır içi tanımlı MCP sunucularını sına: context7'yi data-engineer ile, playwright'ı qa-tester ile. Bağlanmıyorsa nedenini bul (klasör güven onayı, Node.js eksikliği vb.) ve çözüm seçeneklerini bana sor. Playwright'ı ana oturumun .mcp.json dosyasına ekleme; bağlamı şişirir.
3. Projeyi belirgin biçimde hızlandıracak eksik bir MCP sunucusu veya skill görürsen gerekçesiyle öner. Onayım olmadan ekleme.
4. FIRMS_MAP_KEY eksikse MANUAL_TASKS.md'de en üste taşı ve bana tek satırla hatırlat. Anahtarın değerini asla okuma.

Çalışma kuralları:
- Görev verirken CLAUDE.md'deki şablonu kullan. Ajan senin konuşma geçmişini görmez.
- Her görevin başında ve sonunda docs/STATUS.md'yi güncelle ve dosya sahipliğini yaz.
- Ajanlardan yalnızca handoff raporu al. Ayrıntılı raporları gerekmedikçe okuma.
- Benden bir şey gerekirse MANUAL_TASKS.md'ye yaz, bana tek satırla söyle ve bağımsız işlerle devam et.
- Faz sonlarında bana en fazla 8 satırlık özet ver: ne bitti, ne doğrulandı, ne açık, benden ne bekleniyor.
- Bağlam dolmaya yaklaşırsa önce STATUS.md'yi güncelle, sonra bana /compact yazmamı söyle.

Başla: Faz 0 için en fazla 10 satırlık bir plan yaz ve hemen uygula.
```

---

## Sonraki oturumlar için kısa mesaj
Yeni ana oturum açınca önce `/effort max` yazın, sonra:

```text
Ana oturum olarak devam ediyoruz. docs/STATUS.md, docs/PLAN.md ve MANUAL_TASKS.md dosyalarını oku ve kaldığımız yerden devam et. Bir sonraki kontrol noktasında dur ve bana sor.
```

## Kontrol noktalarında örnek cevaplar
- **K1:** `Pilot ilçe: <ad>. Faz 2'yi başlat; F2-1 bitince F2-2…F2-5'i paralel çalıştır.`
- **Başvuru günü (2 Kas):** `pitch-writer ile başvuru taslağını son haline getir; varsa ilk hat haritasının ekran görüntüsünü al.`
- **K2:** `Sonuçları onaylıyorum, Faz 4'e geç.` veya `Ağırlıkları şöyle değiştir: … ve duyarlılık analizini tekrarla.`
- **K3:** `Demo notlarım: … Bunları Faz 5 görevlerine ekle.`
- **Final:** `Final başladı. final-start etiketini at; bundan sonraki her değişikliği FINAL_CHANGELOG'a yaz.`
- **Durum sorma:** `/durum`
