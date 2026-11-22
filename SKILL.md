---
name: promptexe
description: Bir YouTube, Shorts, Instagram Reels ya da TikTok kanal/video linkinden referansın içerik formatını uçtan uca kendisi analiz eder (kanal verisi, orijinal dil transkript, tempo, videonun girişini kare kare izleyip kurgu temposu ve görsel stil, ısı haritası, yorumlar, başlık kalıbı) ve kullanıcının kendi nişi için bu formatı kopyalamadan uygulayan bir instruction / system prompt yazar (Claude Project, Custom GPT, Gemini Gem ya da ham system prompt); istenirse yalnız rakip kanal analiz raporu verir. Her niş, dil ve platformda çalışır. Kullanıcı bir kanal ya da video linki paylaşıp "bu kanal için instruction/prompt yaz", "bu formatı öğren, kendi içeriğime uyarla", "rakip kanalı analiz et", "bu kanal gibi video yazdıracak proje talimatı", "write a channel instruction / system prompt like this channel" dediğinde, açıkça "instruction" demese bile link + kendi içeriğini üretme niyeti varsa bu skill'i kullan. Tek videonun scriptini/kapağını yazmak ya da kendi Studio metriklerini yorumlamak için değildir.
license: MIT
compatibility: Yerel yol için Python 3.9+ ve internet gerekir; yt-dlp ve ffmpeg'i doctor.py kendisi kurar. Ağı kısıtlı ortamlarda (claude.ai, Cowork) bir YouTube analitik MCP bağlayıcısıyla (ör. Nexlev) çalışır.
metadata:
  version: "5.5"
  author: "Ömer Faruk Eynallı"
  credits: "watch_video.py yöntemi watch-skill (MIT) — references/LICENSE-watch-skill.txt"
---

# promptexe

Girdi: referans kanal/video linki. Çıktı: referansın FORMATINI öğrenmiş ama onu kopyalamayan,
kullanıcının konusunda her seferinde taze içerik üreten bir instruction — ya da istenirse
detaylı rakip analiz raporu. Her niş, dil, platform ve kullanıcı için.

## Çalışma felsefesi — önce bunu oku

**Kullanıcı yalnız karar verir; işi skill yapar.** Kullanıcı bu skill'i iş yükünden kurtulmak
için çağırdı. Bu yüzden:

1. **Asla kullanıcıya iş verme.** Kurulum, veri toplama, transkript, izleme, ölçüm, doğrulama
   senin işin. Bir yol tıkanırsa sıradaki yola kendin geç (aşağıdaki yedek zinciri). Kullanıcıdan
   dosya ya da ekran görüntüsü istemek, bütün otomatik yollar tükendiğinde başvurulan son çaredir;
   o zaman da tam olarak neyin neden gerektiğini tek cümleyle söyle.
2. **Yalnız kararları sor, onları da tek seferde ve akıllıca.** Sorular, kullanıcının cevabı
   çıktıyı gerçekten değiştiriyorsa sorulur; çıkarabildiğin hiçbir şeyi sorma (sohbet dili →
   instruction dili, referans sekmesi → format, konuşmada geçen niş → niş). Soruları **analizden
   sonra** sor ki seçenekler veriye dayansın ("Referans 10 dk ortalıyor → 8-10 dk (Önerilen)").
   Soru formu aracını kullan (Claude Code: AskUserQuestion; diğer ortamlarda ekrandaki seçenekli
   soru aracı): en fazla 4 soru, her soruda 2-4 seçenek, önerdiğin seçenek ilk sırada "(Önerilen)"
   etiketiyle, her seçeneğin altında bir satır neden. Serbest metin "Diğer" ile gelir.
3. **Derin düşün, hatasız teslim et.** Sentez ve yazım anları bu işin kalbidir; acele etme.
   Aşağıdaki "Derin düşünme noktaları"nda her birini açıkça düşün. Her ölçüm script'le yapılır,
   her kapı script'le denetlenir; tahmini sayı yazılmaz.
4. **Kredili/ücretli araç kullanımı tek istisnadır:** bağlı bir analitik aracının kredi harcayan
   adımı (ör. video izleme) gerekirse bir kez onay al. Ücretsiz her şeyi sormadan yap.

## Değişmez ilkeler

- **Önce veri, sonra yorum.** Her bulgu "veri" (sayı, alıntı, zaman damgası) ya da "varsayım".
- **Orijinal dil.** Tempo ve anlatım ölçüleri yalnız ses dilindeki metinden; otomatik altyazıda
  isim/sayı çapraz kontrolü.
- **Yapı kopyalanır, malzeme değişir.** Rakip adı, kanal adı ve rakibin cümleleri instruction'a
  girmez (kopya içerik hem etik hem para kazanma riskidir).
- **Hazır şablon yok.** Bölümler ve uzunluklar analizden çıkar.
- **Kapılar script'le denetlenir:** `check_analysis.py` ve `check_instruction.py` GEÇTİ demeden ilerleme.
- **Format:** YouTube 16:9, Shorts/Reels/TikTok 9:16; en-boy oranı araç parametresidir, prompt metnine yazılmaz.
- Rakip kapakları yalnız kullanıcı isterse incelenir. **Teslim:** kopyalanabilir tek sayfa (artifact), yoksa .md.

## Akış

Kontrol listesini cevabına kopyala, ilerledikçe işaretle:

```
- [ ] 1 Ortam hazır (doctor) — sessiz → Yol A (yerel) ya da Yol B (MCP)
- [ ] 2 Otomatik analiz (A: analyze_reference · B: MCP çağrıları + build_from_mcp) + gör + oku
- [ ] 3 TEK FORM: yalnız çıkarılamayan kararlar
- [ ] 4 analiz.json yorumları → check_analysis GEÇTİ → bulgular + uyarlama onayı
- [ ] 5 Instruction → öz-eleştiri → check_instruction GEÇTİ → check_calibration GEÇTİ → teslim
```

### 1 — Ortam (sessiz)
```bash
python3 scripts/doctor.py "<referans_linki>"
```
Eksikleri kendisi kurar (skill-yerel ortam; global kurulum yok), eski yt-dlp'yi günceller.
- `mode: tam` → **Yol A** (yerel, ücretsiz, en zengin: ısı haritası + kendi kare analizin).
- `erisimsiz` / `kurulamadi`, ya da script hiç çalışmıyorsa → **Yol B**: oturumdaki analitik MCP
  aracı (ör. Nexlev). claude.ai / Cowork'te genellikle bu yol olur. Araç adlarını listeden bul.
- İkisi de yoksa: kullanıcıya tek cümleyle bir analitik bağlayıcısı (ör. Nexlev) eklemesini öner;
  o gelene kadar kullanıcının verdiği link/metinlerle sınırlı analiz yap ve bunu söyle.
Kullanıcıya yalnız "veriyi şuradan çekiyorum" de; kurulum ayrıntısı anlatma.

### 2 — Otomatik analiz (soru sormadan)
**Yol A (yerel):**
```bash
python3 scripts/analyze_reference.py "<link>" --outdir analiz
```
Tek komut: kanal haritası (sekme bazlı outlier), en iyi 3 + en zayıf 1 video, orijinal dil
transkript + tempo, bölümler, ısı haritası, yorumlar, girişin kareleri + orta bölüm kurgu temposu.
`analiz/analiz.json` ölçümlerle dolu gelir. Sonra **sen**: temas sayfasını (gerekirse kareleri tek
mesajda paralel) Read ile aç; transkriptleri oku; otomatik altyazıysa `capraz_dosya` ile kontrol et.
`eksikler` doluysa sıradaki yedeğe kendin geç (veri-toplama.md). "Çevrilmiş başlık" uyarısı varsa başlık
kalıbını yalnız `videolar[].meta.baslik` ile incele; `konusma_yok` işaretli video anlatımsızdır (format farkı, bulgu).

**Yol B (MCP):** `references/mcp-yolu.md`'yi oku ve oradaki çağrı sırasını uygula (çevrilmiş
başlık, yaklaşık tarih ve otomatik altyazı tuzaklarına dikkat). Toplananları kısa `mcp_veri.json`'a
ve transkript dosyalarına yaz, sonra `python3 scripts/build_from_mcp.py mcp_veri.json --outdir analiz`
→ aynı şemada `analiz.json`.

Buradan sonrası iki yolda aynı. Yorumlama rehberi: `references/analiz-rehberi.md`,
`references/dagitim-mantigi.md`, `references/kanal-tipleri.md`.

### 3 — Tek akıllı form
Konuşmadan ve analizden çıkaramadıklarını tek formda sor. Tipik adaylar (çıkarabildiklerini at):
- **Kendi konusu/nişi** — referansın konusuna yakın 2-3 uyarlama önerisi + "Diğer"
- **Hedef süre** — referansın medyanından türet (Önerilen) + bir kısa bir uzun alternatif
- **Instruction'ın kullanılacağı yer** — Claude Project (Önerilen) / Custom GPT / Gemini Gem / ham system prompt
- **Görsel üretim yöntemi / yüzlü-yüzsüz** — yalnız format ardışık görsel ya da kamera gerektiriyorsa

Kullanıcı "sadece analiz" dediyse formu atla, 4. adımdaki raporu teslim et ve dur.

### 4 — Analizi tamamla ve onaylat
Formdan hemen sonra, soru sormadan iki ölçüm daha (paralel çalıştırılabilir):
```bash
# Bölüm bütçesi: hedef süre + referans transkriptleri → her bölüm için süre · kelime · karakter
python3 scripts/section_budget.py --target <hedef_süre> analiz/tr/*.txt \
  --section "Giriş=0s:40s" --section "Gövde 1=40s:25%" … --section "Kapanış=92%:100%" \
  --json > analiz/butce.json
# Piyasa konu havuzu: nişte tutmuş benzer videolar (Yol B: mcp-yolu.md §5)
python3 scripts/market_topics.py "<niş sorgusu 1>" "<sorgu 2>" --exclude "<referans kanal>" --lang <içerik dili> \
  [--shorts | --min-duration <referans medyan süresinin yarısı, sn>] --out analiz/piyasa.json
```
Bölüm sınırlarını referansın gerçek iskeletinden (bölümler, transkript) seç; içerik dili farklıysa
`--lang-factor` (instruction-yazimi.md ilke 10). Piyasa verisi hiçbir yoldan gelmezse
`analiz.json`'a `"piyasa_durumu": "yok"` yaz. Sonra `analiz.json`'daki yorum alanlarını doldur (izleme.gozlem, transkriptle_uyum, capraz_kontrol,
kategori, kanal_tipi, ≥6 bulgu, uyarlama, kullanici, tempo.hedef_kelime = hedef süre × kelime/dk):
```bash
python3 scripts/check_analysis.py analiz/analiz.json
```
GEÇMEDİ → eksik veriyi kendin tamamla (ölç, çek, izle), varsayımla doldurma. GEÇTİ → analiz
raporunu (analiz-rehberi.md §3) sun ve tek soruyla onaylat: "Uyarlama böyle mi?" — gerekiyorsa
aynı formda sahne sayısı seçeneği (süre ÷ kesim sıklığından hesaplanmış öneriyle).

### 5 — Instruction
`references/instruction-yazimi.md`'yi oku; `assets/ornek-instruction.md` kalite ölçüsüdür, şablon
değil. Seçilen hedefin uzunluk sınırına uy (instruction-yazimi.md §5). Yaz → öz-eleştiri → kapı:
```bash
python3 scripts/check_instruction.py instruction.md analiz/analiz.json analiz/tr/*.txt --target <claude|gpt|gem|system>
```
GEÇTİ → **kalibrasyon**: instruction'ı kullanarak 3 farklı konuda giriş yaz (`kalibrasyon.md`,
her biri `## Örnek N — <konu>` + ```` ```text ```` bloğu, yalnız seslendirilecek metin) ve ölç:
```bash
python3 scripts/check_calibration.py kalibrasyon.md --budget analiz/butce.json --section "Giriş" \
  --sabit "<sabit selam>" --sabit "<sabit gag>"
```
Uzunluk sapması → örneği düzelt. Benzerlik → talimattaki çeşitlilik kuralını düzelt. Rapora script'in
sayılarını yaz; kendi yazdığın metnin uzunluğunu gözle tahmin etme (sistematik olarak fazla sayarsın).
GEÇTİ → teslim. Teslim
notunda: hangi kuralların varsayıma dayandığı ve kullanıcının kendi Studio verisiyle neyi
doğrulaması gerektiği.

## Derin düşünme noktaları

Bu anlarda cevap vermeden önce açıkça düşün:

1. **Kategori ve kanal tipi** — dağılım (outlier oranı, eski videoların izlenmesi), ısı haritası ve
   başlıklar aynı şeyi mi söylüyor? Çelişiyorsa hangisine neden güveniyorsun?
2. **Kimlik mi tembellik mi** — her tekrarlayan kalıp için: bu kanalı kanal yapan bir şey mi, yoksa
   seri üretim izi mi? Kimlik taşınır, tembellik taşınmaz.
3. **Kazanan/kaybeden farkı** — en zayıf video popülerlerden tam olarak neyle ayrılıyor (konu,
   başlık vaadi, giriş, süre)? Bu fark instruction'da bir kurala dönüşmeli.
4. **Uyarlama** — referansın işleyen mekanizması kullanıcının nişinde hangi karşılığa sahip?
   Birebir taşınamayan öğe için en yakın işlevsel eşdeğer ne?
5. **Öz-eleştiri (yazdıktan sonra, kapıdan önce)** — instruction'ı hiç görmemiş bir Claude gibi
   oku: her kural ölçülebilir, gerekçeli, konudan bağımsız mı? Dayanağı analizde olmayan kural var
   mı? İki farklı konuda iki çok benzer script üretir mi? Bulduğun her sorunu düzelt, sonra kapıyı çalıştır.

## Dosyalar

| Dosya | Ne zaman |
|---|---|
| `scripts/doctor.py` | 1 — ortamı kendisi kurar/günceller |
| `scripts/analyze_reference.py` | 2, Yol A — tüm ölçülebilir analiz, tek komut |
| `scripts/build_from_mcp.py` + `references/mcp-yolu.md` | 2, Yol B — MCP verisinden aynı `analiz.json` |
| `scripts/fetch_channel.py`, `fetch_transcript.py`, `transcript_stats.py`, `watch_video.py` | Tek tek gerekirse (hat bunları zaten çağırır) |
| `scripts/section_budget.py` | 4 — bölüm başına süre · kelime · karakter bütçesi |
| `scripts/market_topics.py` | 4 — piyasada tutmuş benzer videolar (konu havuzu B) |
| `scripts/check_analysis.py`, `check_instruction.py`, `check_calibration.py` | 4 ve 5 — kapılar |
| `references/veri-toplama.md` | Yedek zinciri, analitik aracı eşlemesi, ortam sınırları |
| `references/analiz-rehberi.md` | Ne çıkarılır, `analiz.json` şeması, rapor formatı |
| `references/dagitim-mantigi.md`, `kanal-tipleri.md` | Kategori, giriş, başlık, uyum; kanal tipi modülleri |
| `references/instruction-yazimi.md` | Bölümler, zorunlu ilkeler, kalite çıtası, hedef platform sınırları |
| `assets/ornek-instruction.md` | Kalite ölçüsü (şablon değil) |

Script yolları bu skill klasörüne göredir (Claude Code'da `${CLAUDE_SKILL_DIR}/scripts/…`).
Script'ler kendilerini doctor'ın kurduğu ortamda yeniden başlatır; hangi python ile çağrıldıkları önemsizdir.
