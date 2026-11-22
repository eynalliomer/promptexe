#!/usr/bin/env python3
"""Bir videonun ORİJİNAL DİL transkriptini çeker (yt-dlp), gerekirse sesten üretir.

Kullanım:
    python3 fetch_transcript.py <video_linki> [--lang es] [--also en] [--outdir tr/] [--asr]

Sıra:
  1. Mevcut altyazı dillerini listeler; videonun ses dilini (yt-dlp 'language' alanı ya da
     --lang) belirler. Çoğu araç İngilizceyi ya da ilk parçayı döndürür — bu yüzden dil açık seçilir.
  2. Ses dilindeki altyazıyı (elle yazılmış varsa o, yoksa otomatik/ASR) indirir.
  3. --also ile ikinci dili (ör. en) çapraz kontrol için indirir.
  4. Altyazı yoksa ve --asr verildiyse sesi indirip faster-whisper ile yazıya döker.

Çıktı: <outdir>/<id>.<dil>.txt (zaman damgalı satırlar "[mm:ss] metin") ve
<outdir>/<id>.meta.json (dil, kaynak türü: manual|auto|asr, süre, başlık).
"""
import argparse
import glob
import html
import json
import os
import re
import subprocess
import sys
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import _env  # noqa: E402
_env.ensure_venv_python()


def sh(cmd, timeout=600):
    if cmd and cmd[0] == "yt-dlp":
        cmd = _env.ytdlp_base() + cmd[1:]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        sys.exit(f"HATA: {cmd[0]} kurulu değil.")


def vtt_to_lines(path):
    """VTT -> [(saniye, metin)]. Otomatik altyazılardaki kayan tekrarları ayıklar."""
    lines, last = [], ""
    cur_t = 0.0
    ts = re.compile(r"(\d+):(\d+):(\d+)\.(\d+)\s+-->")
    with open(path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            m = ts.match(raw)
            if m:
                h, mi, s, ms = map(int, m.groups())
                cur_t = h * 3600 + mi * 60 + s + ms / 1000
                continue
            if not raw or raw.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or raw.isdigit():
                continue
            text = html.unescape(re.sub(r"<[^>]+>", "", raw)).replace("\xa0", " ").strip()
            text = re.sub(r"\s+", " ", text)
            if text and text != last:
                lines.append((cur_t, text))
                last = text
    # Otomatik altyazıda bir satır bir sonrakinin başı olarak tekrar eder; birleştir.
    dedup = []
    for t, x in lines:
        if dedup and x.startswith(dedup[-1][1]):
            dedup[-1] = (dedup[-1][0], x)
        elif dedup and dedup[-1][1].endswith(x):
            continue
        else:
            dedup.append((t, x))
    return dedup


def write_txt(lines, path):
    with open(path, "w", encoding="utf-8") as f:
        for t, x in lines:
            f.write(f"[{int(t // 60):02d}:{int(t % 60):02d}] {x}\n")


def fetch_subs(url, lang, outdir, vid):
    """Önce elle yazılmış, yoksa otomatik altyazı. Döner: (yol, tür) ya da (None, None)."""
    for kind, flag in (("manual", "--write-subs"), ("auto", "--write-auto-subs")):
        sh(["yt-dlp", "--skip-download", flag, "--sub-langs", f"{lang}.*,{lang}",
            "--sub-format", "vtt", "--no-warnings", "-o", os.path.join(outdir, "%(id)s.%(ext)s"), url])
        found = sorted(glob.glob(os.path.join(outdir, f"{vid}.{lang}*.vtt")))
        # Otomatik çeviri parçalarını ("en-es" gibi) değil, asıl dili tercih et
        found = [p for p in found if re.search(rf"\.{lang}(-orig)?\.vtt$", p)] or found
        if found:
            return found[0], kind
    return None, None


def asr(url, outdir, vid, lang):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        # Kullanıcıya iş bırakma: skill ortamındaysak kendimiz kuralım (büyük paket, yalnız gerektiğinde)
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "faster-whisper"], capture_output=True, text=True)
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            sys.exit("HATA: altyazı yok ve faster-whisper kurulamadı — MCP yolunun transkript aracına geç "
                     "(references/mcp-yolu.md).")
    audio = os.path.join(outdir, f"{vid}.m4a")
    for attempt in range(2):  # paralel koşuda geçici 429 olabiliyor: bir kez bekleyip yeniden dene
        r = sh(["yt-dlp", "-f", "bestaudio[ext=m4a]/bestaudio", "-o", audio, "--no-warnings", url], timeout=1200)
        if r.returncode == 0 and os.path.exists(audio):
            break
        import time
        time.sleep(8)
    if r.returncode != 0 or not os.path.exists(audio):
        sys.exit("HATA: ses indirilemedi (ortam YouTube'a erişemiyor olabilir) — MCP yoluna geç (references/mcp-yolu.md).")
    # 'small' model: CPU'da makul hız, özel adlarda 'base'den belirgin iyi.
    model = WhisperModel("small", device="cpu", compute_type="int8")
    # Sesi ffmpeg ile 16 kHz mono float diziye çevirip ver: faster-whisper'ın kendi çözücüsü (PyAV)
    # yeni av sürümlerinde 'metadata_errors' hatasıyla çöküyor (2026-11-12, av 19).
    try:
        import numpy as np
        raw = subprocess.run([_env.ffmpeg_path(), "-v", "error", "-i", audio, "-f", "s16le", "-ac", "1",
                              "-ar", "16000", "-"], capture_output=True).stdout
        source = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    except Exception:
        source = audio
    # vad_filter: konuşmasız (yalnız müzik/efekt) kısımları atlar; yoksa Whisper gürültüden metin uydurur
    # ve dili de uydurur (2026-11-12: müzikli bir Short "nn" + "KÖHÄÄÄ…" verdi).
    segs, info = model.transcribe(source, language=lang, vad_filter=True)
    lines = [(s.start, s.text.strip()) for s in segs if s.text.strip() and (s.no_speech_prob or 0) < 0.6]
    words = sum(len(t.split()) for _, t in lines)
    sure = lang or (info.language if (info.language_probability or 0) >= 0.5 else None)
    return lines, sure, words


def main():
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--lang", help="ses dili (ör. es, tr, en). Verilmezse yt-dlp'nin tespiti kullanılır")
    p.add_argument("--also", help="çapraz kontrol dili (ör. en)")
    p.add_argument("--outdir", default="transcripts")
    p.add_argument("--asr", action="store_true", help="altyazı yoksa sesten yazıya dök")
    p.add_argument("--lang-hint", help="video dil bilgisi vermezse kullanılacak dil (ör. kanalın diğer videolarınınki)")
    p.add_argument("--info-json", help="önceden çekilmiş yt-dlp -J çıktısı (aynı videoyu iki kez çekmemek için)")
    a = p.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    info = None
    if a.info_json:
        try:
            info = json.load(open(a.info_json, encoding="utf-8"))
        except (OSError, ValueError):
            info = None
    if not info:
        r = sh(["yt-dlp", "--dump-json", "--skip-download", "--no-warnings", a.url])
        if r.returncode != 0:
            sys.exit("HATA: video bilgisi alınamadı: " + (r.stderr.strip().splitlines() or ["?"])[-1])
        info = json.loads(r.stdout)
    vid = info["id"]
    lang = a.lang or (info.get("language") or "").split("-")[0] or None
    manual = sorted((info.get("subtitles") or {}).keys())
    auto_langs = info.get("automatic_captions") or {}
    # Otomatik altyazılarda "-orig" eki videonun gerçek ses dilini işaret eder
    orig = [k.replace("-orig", "") for k in auto_langs if k.endswith("-orig")]
    if not lang and orig:
        lang = orig[0]
    if not lang and len(manual) == 1:
        lang = manual[0].split("-")[0]  # tek elle altyazı dili → büyük olasılıkla ses dili
    asr_first = None
    if not lang:
        if not a.asr:
            sys.exit(f"HATA: ses dili tespit edilemedi. --lang ile ver. Elle altyazılar: {manual}; "
                     f"otomatik (orijinal işaretli): {orig}")
        # Ne dil bilgisi ne altyazı var (2026-11-12: altyazısız Shorts): Whisper dili kendisi tespit eder
        asr_first, lang, _w = asr(a.url, a.outdir, vid, None)
        lang = lang or a.lang_hint or "und"

    meta = {"id": vid, "title": info.get("title"), "duration_s": info.get("duration"),
            "audio_lang": lang, "manual_sub_langs": manual, "orig_auto_langs": orig, "files": {}}

    # Tek yt-dlp çağrısı: ses dili + çapraz kontrol dili, elle yazılmış varsa o, yoksa otomatik.
    # (Eskiden dil × tür başına ayrı çağrı vardı: video başına 4-5 çağrı.)
    langs = [lang] + ([a.also] if a.also and a.also != lang else [])
    # Ses dilinin elle yazılmış bölgesel varyantı (en-GB, en-US …) varsa tam anahtarı da kullan
    variant = next((k for k in manual if k.startswith(lang + "-") and not k.endswith("-orig")), None)
    if lang not in manual and variant:
        langs[0] = variant
        lang_req = variant
    else:
        lang_req = lang
    if asr_first is None or a.also:
        sh(["yt-dlp", "--skip-download", "--write-subs", "--write-auto-subs",
            "--sub-langs", ",".join(f"{l},{l}-orig" for l in langs), "--sub-format", "vtt",
            "--no-warnings", "-o", os.path.join(a.outdir, "%(id)s.%(ext)s"), a.url])

    def pick_file(l):
        found = sorted(glob.glob(os.path.join(a.outdir, f"{vid}.{l}*.vtt")))
        found = [f for f in found if re.search(rf"\.{re.escape(l)}(-orig)?\.vtt$", f)]
        if not found:
            return None, None
        manual_keys = info.get("subtitles") or {}
        # Elle yazılmış sayılması için TAM bu dil anahtarı elle altyazılarda olmalı. "en-GB" elle varken
        # indirilen "en" dosyası otomatiktir (2026-11-12: noktalamasız metin "manual" etiketlenmişti).
        exact = [f for f in found if not f.endswith("-orig.vtt")]
        if l in manual_keys and exact:
            return exact[0], "manual"
        return found[0], "auto"

    path, kind = (None, None) if asr_first is not None else pick_file(lang_req)
    if asr_first is None and not path and (info.get("automatic_captions") or info.get("subtitles")):
        # Altyazı listede var ama inmedi: paralel çağrılarda geçici 429 olabilir → bir kez bekleyip yeniden dene
        import time
        time.sleep(3)
        sh(["yt-dlp", "--skip-download", "--write-subs", "--write-auto-subs",
            "--sub-langs", ",".join(f"{l},{l}-orig" for l in langs), "--sub-format", "vtt",
            "--no-warnings", "-o", os.path.join(a.outdir, "%(id)s.%(ext)s"), a.url])
        path, kind = pick_file(lang_req)
    if not path and asr_first is None:
        path, kind = fetch_subs(a.url, lang, a.outdir, vid)  # yedek: eski tek tek deneme
    if asr_first is not None:
        lines, kind = asr_first, "asr"
        meta["asr_detected_lang"] = lang
    elif path:
        lines = vtt_to_lines(path)
    elif a.asr:
        lines, detected, _w = asr(a.url, a.outdir, vid, lang)
        kind = "asr"
        meta["asr_detected_lang"] = detected
    else:
        sys.exit(f"HATA: '{lang}' altyazısı yok. --asr ile sesten üret ya da MCP transkript aracına geç.")
    if kind == "asr" and sum(len(t.split()) for _, t in lines) < 5:
        # Konuşma yok: metin yazılmaz, video "konuşmasız" işaretlenir — bu bir bulgudur, hata değil
        lines = []
        meta["konusma_yok"] = True
        meta["warning"] = "Videoda anlatım/konuşma yok (yalnız müzik ya da efekt). Tempo ölçülmez; format farkı olarak not et."
    out = os.path.join(a.outdir, f"{vid}.{lang}.txt")
    write_txt(lines, out)
    meta["files"][lang] = {"path": out, "source": kind}
    if kind in ("auto", "asr") and not meta.get("konusma_yok"):
        meta["warning"] = "Otomatik metin: özel adlar/sayılar hatalı olabilir — çapraz kontrol et."

    if a.also and a.also != lang:
        p2, k2 = pick_file(a.also)
        if p2:
            out2 = os.path.join(a.outdir, f"{vid}.{a.also}.txt")
            write_txt(vtt_to_lines(p2), out2)
            meta["files"][a.also] = {"path": out2, "source": k2}
        else:
            meta["also_missing"] = f"'{a.also}' altyazısı yok; çapraz kontrolü başlık/açıklama ve izleme notuyla yap."

    with open(os.path.join(a.outdir, f"{vid}.meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
