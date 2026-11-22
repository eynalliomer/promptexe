# promptexe

Bir Claude skill'i (Agent Skill). Bir YouTube, Shorts, Instagram Reels ya da TikTok kanal/video
linkinden referansın içerik formatını uçtan uca analiz eder ve kendi nişin için bu formatı
**kopyalamadan** uygulayan bir instruction / system prompt yazar (Claude Project, Custom GPT,
Gemini Gem ya da ham system prompt). İstenirse yalnız rakip kanal analiz raporu verir.

*A Claude Agent Skill that analyses a reference channel's content format (transcript, pacing,
edit tempo, hooks, titles, heatmap, comments) and writes a channel instruction / system prompt
that applies the format to your own niche without copying it. Instructions are in Turkish; the
skill works for any language and platform.*

## Ne yapar

- Kanal haritası: en iyi 3 + aynı formattan en zayıf 1 video (yan seriler ve farklı dildeki videolar elenir)
- Orijinal dilde transkript (elle altyazı → otomatik altyazı → Whisper), konuşma temposu
- Videonun girişini kare kare izler: kurgu temposu, yumuşak geçiş ölçümü, görsel stil
- Isı haritası, bölümler, yorumlar, başlık kalıbı (çevrilmiş başlık uyarısıyla)
- Bölüm bütçesi (süre · kelime · karakter) ve nişte tutmuş videolardan konu havuzu
- Script'le denetlenen üç kapı: analiz, instruction ve kalibrasyon

Kullanıcıya yalnız karar soruları sorulur; kurulum, veri toplama ve ölçüm skill'in işidir.

Nasıl çalıştığı, veri yolları ve kapılar: [ARCHITECTURE.md](ARCHITECTURE.md) · sürüm geçmişi:
[CHANGELOG.md](CHANGELOG.md).

## Kurulum

**Claude Code:**

```bash
git clone https://github.com/eynalliomer/promptexe ~/.claude/skills/promptexe
```

**claude.ai:** [Releases](https://github.com/eynalliomer/promptexe/releases) sayfasından
`promptexe.skill` dosyasını indir, Ayarlar → Capabilities → Skills'ten yükle. Ağı kısıtlı
ortamlarda skill bir YouTube analitik MCP bağlayıcısıyla (ör. Nexlev) çalışır.

Gereksinim: Python 3.9+ ve internet. `yt-dlp` ve `ffmpeg`'i `scripts/doctor.py` skill'e özel bir
ortama kendisi kurar.

## Kullanım

Claude'a bir kanal ya da video linki ver ve ne istediğini söyle:

> "Bu kanal gibi video yazdıracak bir proje talimatı yaz: https://www.youtube.com/@kanal"

## Sorumluluk

Skill bir formatın *yapısını* öğrenir; rakibin adını, kanal adını ve cümlelerini çıktıya taşımaz.
Ürettiğin içeriğin platform kurallarına ve telif haklarına uygunluğu senin sorumluluğundadır.

## Lisans

MIT © 2026 Ömer Faruk Eynallı — bkz. [LICENSE](LICENSE). `scripts/watch_video.py` yöntemi
[watch-skill](https://github.com/oxbshw/watch-skill)'den (MIT) uyarlanmıştır:
[references/LICENSE-watch-skill.txt](references/LICENSE-watch-skill.txt).
