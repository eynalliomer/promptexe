---
title: Veri toplama — araç seçimi ve yedek yollar
---

# Veri toplama

**Ne zaman oku:** 1-2. adımda, bir veri yolu tıkandığında.

Kural: **veriyi sen toplarsın, kullanıcı değil.** Sıra:

1. `doctor.py` → `mode: tam` ise `analyze_reference.py` her şeyi tek komutta yapar (ücretsiz).
2. `erisimsiz` / `kurulamadi` ya da hattın `eksikler` listesi doluysa → oturumdaki analitik aracı
   (MCP, ör. Nexlev): tam çağrı sırası, tuzaklar ve `build_from_mcp.py` → **`mcp-yolu.md`**.
   Araç adlarını tahmin etme, listeden bul. Kredili adımlar için bir kez onay al.
3. Bir adım hâlâ eksikse aşağıdaki tablodaki diğer yollar.
4. **Son çare** kullanıcıdan veri: yalnız bütün otomatik yollar tükendiyse, tam olarak neyin neden
   gerektiğini tek cümleyle iste (ör. "Bu ortam YouTube'a erişemiyor ve bağlı analitik aracı yok;
   videonun ilk 40 saniyesinden 4-5 ekran görüntüsü atarsan girişi onlardan okurum").

Her adımın sonunda verinin nereden geldiğini `analiz.json` → `veri_kaynagi`'na yaz.

## Adım → araç → yedek yol

| Adım | Analitik aracı varsa (ör. Nexlev MCP) | Yoksa — bu skill'in script'leri | O da olmazsa |
|---|---|---|---|
| Kanal kimliği | `channel_resolver` (UC… ID) | `fetch_channel.py` linki doğrudan alır | Kullanıcıdan kanal linki |
| Kanal hakkında, popüler/yeni, outlier | `youtube_channel_about`, `youtube_channel_videos`, `youtube_channel_outliers`, `check_faceless_channel` | `python3 scripts/fetch_channel.py <link> --limit 30 --out kanal.json` | Kullanıcıdan "Videolar" sekmesinin ekran görüntüsü (izlenme + tarih görünsün) |
| Altyazı dilleri + transkript | `get_video_subtitle` / `get_video_transcript` / `get_bulk_video_transcripts` — **dil parametresiyle** | `python3 scripts/fetch_transcript.py <video> --also en --outdir tr/` | `--asr` (sesten, faster-whisper) ya da kullanıcının yüklediği ses/video/metin |
| İlk 30–40 sn izleme | **Önce** `python3 scripts/watch_video.py <video> --end 40` (ücretsiz; kesimler + kareler + temas sayfası, sen görürsün). İndiremezse `watch_youtube_video_and_ask` (ofset almıyorsa pencereyi istemde yaz) — **kredili, tek sefer** | Kullanıcının verdiği dosya: `watch_video.py ~/rakip.mp4 --end 40`; ya da 3–5 ekran görüntüsü | Transkriptin ilk 40 sn'si + başlık/kapak (gözlem "izlenmedi" olarak işaretlenir) |
| Görsel tempo (tüm video) | — | `watch_video.py <video> --start <orta> --end <orta+60> --cuts-only` → kesim/dk, ortalama plan süresi | Varsayım olarak işaretle |
| Tempo ve anlatım ölçüsü | — | `python3 scripts/transcript_stats.py tr/<id>.<dil>.txt --lang <dil> --hook 40` | Elle sayım (son çare) |
| Instagram / TikTok | `watch_instagram_video_and_ask`, `watch_tiktok_video_and_ask` | `fetch_channel.py` profil linkiyle (Instagram çoğu zaman `--cookies-from-browser chrome` ister) | Kullanıcıdan profil SS + 2–3 video linki/dosyası |

Script'ler `scripts/` altında; yolları skill klasörüne göredir (Claude Code'da `${CLAUDE_SKILL_DIR}/scripts/…`).
Gereken: `yt-dlp` (ve `--asr` için `faster-whisper`, `ffmpeg`). Kurulu değilse kullanıcıya kurulum
komutunu söyle; global kurulum yerine sanal ortam öner.

## Orijinal dil — neden bu kadar önemli

Tempo (kelime/dk), cümle uzunluğu ve kancanın sözcük seçimi **yalnız ses dilindeki metinden**
ölçülür; çeviri metin kelime sayısını %10–30 kaydırır ve kural yanlış çıkar. Çoğu araç
varsayılan olarak İngilizceyi ya da ilk parçayı döndürür. Bu yüzden:

1. Önce altyazı parçalarını listele, ses dilini belirle (`fetch_transcript.py` bunu `-orig` işaretinden yapar).
2. Ses dilindeki parçayı iste. Bu çoğu zaman otomatik (ASR) altyazıdır → özel ad ve sayılar hatalı olabilir.
3. Varsa İngilizce (ya da elle yazılmış) parçayla **cümle, sayı ve isim** bazında çapraz kontrol et,
   düzeltilmiş metinden kural çıkar; yaptığın düzeltmeleri `capraz_kontrol` alanına yaz.

## İzleme — `watch_video.py` nasıl okunur

- `cuts_per_min`, `avg_shot_s`: kurgu temposu. **Animasyonda dikkat:** aynı fon üzerinde karakter
  hareketi kesim sayılmaz (eşik 0.3), bu yüzden çizgi/animasyon kanallarında kesim sayısı düşük
  çıkar — tempoyu karelerdeki değişimden de oku.
- `frames`: kesim sonrası kareler (`kesim`) + düzenli aralıklı kareler; tekrar eden kareler
  ayıklanmış. Zaman damgası dosya adında (`t00m13.85s.jpg`).
- Kareleri açınca çıkar: görsel tür (çizim/AI/gerçek çekim/stok), ekran yazısı ve dili, palet,
  kompozisyon, başlık kartı ya da kanal jeneriğinin zamanı, yüz var mı.
- Bu gözlemleri `analiz.json` → `izleme`'ye yaz (`kaynak: watch_video`, `kesim_dk`, `kareler`).
- yt-dlp YouTube'da 403 verirse önce `doctor.py`'yi yeniden çalıştır (30 günden eski yt-dlp'yi kendisi
  günceller). Güncel sürümle de olmuyorsa engeli aşmaya çalışma — MCP yoluna geç.

Yöntem: [watch-skill](https://github.com/oxbshw/watch-skill) (MIT) — bkz. `LICENSE-watch-skill.txt`.

## Ortam sınırları

- **claude.ai / Cowork:** ağ erişimi yönetici ayarına bağlı; YouTube çoğu zaman sunucu IP'sini
  engeller ("Sign in to confirm you're not a bot"). Engeli aşmaya çalışma — analitik aracına
  geç (`mcp-yolu.md`); kullanıcıdan veri yalnız son çare.
- **Claude Code (yerel):** script'ler tam çalışır.
- **API:** ağ yok → yalnız kullanıcının verdiği dosyalarla.

## Maliyet

Video izleme araçlarının günlük hakkı/kredisi sınırlıdır: yalnız en çok izlenen videonun ilk
30–40 sn'si, tek sefer. Transkript ve kanal listesi ucuzdur; izlemeden önce onları bitir ki
izleme sorusu net olsun.
