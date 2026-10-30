# Durum panosu

Orkestratör günceller. Oturum başında ve bağlam sıkıştırıldıktan sonra ilk okunacak dosya budur.

**Son güncelleme:** 2026-10-30 — F0 sürüyor. F0-1 sözdizimi denetimi bitti; oturum proje köküne taşınıyor.

## Fazlar
| Faz | Durum | Not |
|---|---|---|
| F0 Kurulum denetimi | 🔄 | F0-1: 10 ajan + 6 skill frontmatter'ı geçerli (BOM yok, bloklar kapalı; `durum` bilinçli olarak yalnız kullanıcıya açık). Ajanların görünürlüğü taşımadan sonra denetlenecek. F0-2…F0-4 taşımadan sonra başlayacak |
| F1 Veri keşfi + pilot seçimi | ⬜ | K1: pilot ilçe |
| F1B Başvuru taslağı | ⬜ | Taslak hedefi 1 Kas akşamı · başvuru son tarihi 2 Kas 23:59 |
| F2 Veri hattı | ⬜ | |
| F3 Risk modeli | ⬜ | K2: sonuçlar |
| F4 API + arayüz | ⬜ | K3: demo provası |
| F5 Demo cilası + sunum | ⬜ | |
| F6 Final | ⬜ | 15–16 Kas |

Durum simgeleri: ⬜ başlamadı · 🔄 sürüyor · ✅ bitti · ⛔ engelli

## Aktif görevler
| ID | Ajan | Durum | Sahip olduğu dosyalar | Rapor |
|---|---|---|---|---|
| F0-1 | orkestratör | 🔄 | .claude/agents/*.md, .claude/skills/*/SKILL.md, MANUAL_TASKS.md, docs/STATUS.md | — |

## Biten görevler
| ID | Ajan | Sonuç | Rapor |
|---|---|---|---|
| — | — | — | — |

## Engeller
- **Oturum yanlış klasörde açılmıştı.** Oturum `Desktop\hatkalkani` klasöründeydi; proje kökü `Desktop\hatkalkani\hatkalkani`. Bu yüzden 10 proje ajanı, `.claude/settings.json` ve CLAUDE.md yüklenmedi (5 skill iç içe keşifle göründü). Çözüm: oturum 30 Eki'de proje köküne taşınıyor; ardından ajan listesi yeniden denetlenecek.

## İzlenecekler
- F0-3: `playwright` MCP `command: npx` ile tanımlı; Windows'ta `cmd /c` sarmalayıcısı gerekebilir. qa-tester'ın `tools` alanındaki `mcp__playwright__*` joker deseni de bu testte sınanacak.
- ECC GateGuard kancası her yeni dosyaya ilk yazmada ve ilk kabuk komutunda "Fact-Forcing Gate" ile durduruyor. Alt ajan görevlerine "bilgileri yaz, aynı aracı aynı mesajda yeniden çağır" notu eklenecek.

## Kullanıcıdan beklenenler
MANUAL_TASKS.md'ye bak. En acil olanlar: FIRMS_MAP_KEY ve `.env` (#4, #5).

## Önemli sonuçlar (sayılar, kaynak dosyasıyla)
- henüz yok

## Model yükseltmeleri
Hangi görev neden Opus'a yükseltildi:
- yok
