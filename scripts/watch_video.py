#!/usr/bin/env python3
"""Bir videonun belirli bir penceresini "izler": sahne kesimlerini ölçer, zaman damgalı
kareler ve bir temas sayfası (contact sheet) çıkarır. Claude kareleri Read ile görür.

Kullanım:
    python3 watch_video.py <video_linki_veya_dosya> [--start 0] [--end 40] [--max-frames 16]
                           [--outdir izleme/] [--cuts-only]

Örnekler:
    # Giriş (ilk 40 sn): kesimler + 16 kareye kadar
    python3 watch_video.py https://youtu.be/XXXX --end 40
    # Orta bölümden 60 sn'lik örnek: yalnız kesim temposu
    python3 watch_video.py https://youtu.be/XXXX --start 300 --end 360 --cuts-only
    # Kullanıcının verdiği dosya
    python3 watch_video.py ~/Downloads/rakip.mp4 --end 40

Çıktı (stdout JSON + <outdir>/watch.json):
  window, cuts (sn), cuts_per_min, avg_shot_s, frames [{t, path, reason}], contact_sheet.
  Sonra: frames listesindeki dosyaları TEK mesajda paralel Read ile aç, gözlemi aynı
  penceredeki transkript satırlarıyla karşılaştır.

Gereken araçları scripts/doctor.py kurar (skill-yerel yt-dlp + gerekirse taşınabilir ffmpeg);
bu script onları _env.py üzerinden bulur. Yalnız standart kütüphane.

Yöntem kaynağı: watch-skill (github.com/oxbshw/watch-skill, MIT, © 2026 oxbshw) —
ffmpeg sahne eşiği 0.3, kesim başı + düzenli doldurma kareleri, algısal hash ile tekrar
kare ayıklama, pencere süresine göre kare bütçesi. Kod bu skill için baştan yazıldı;
lisans metni: references/LICENSE-watch-skill.txt
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import _env  # noqa: E402
_env.ensure_venv_python()

SCENE_THRESHOLD = 0.3   # watch-skill varsayılanı; 0.2 gürültülü (ışık değişimi), 0.4 yumuşak geçişleri kaçırır
DHASH_MAX_DIST = 6      # 64 bitlik dHash'te ≤6 bit fark = aynı kare sayılır
CUT_OFFSET = 0.25       # kesimin hemen sonrası: geçiş karesini (blur/fade) değil yeni sahneyi al


def run(cmd, timeout=900):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        sys.exit(f"HATA: zaman aşımı: {' '.join(cmd[:3])}…")


def acquire(src, start, end, outdir):
    """Yerel dosya ise olduğu gibi; URL ise yalnız penceriyi düşük çözünürlükte indir."""
    if os.path.exists(os.path.expanduser(src)):
        return os.path.expanduser(src), start  # dosyada mutlak zaman korunur
    out = os.path.join(outdir, "pencere.%(ext)s")
    r = run(_env.ytdlp_base() + ["-q", "--no-warnings", "--no-playlist",
             # 360p yeterli: kesim tespiti ve kompozisyon için; 1080p indirmek 10x zaman
             "-f", "bv*[height<=360][ext=mp4]/bv*[height<=360]/b[height<=360]/b",
             "--download-sections", f"*{start}-{end}", "-o", out, "--", src])
    files = [f for f in os.listdir(outdir) if f.startswith("pencere.")]
    if r.returncode != 0 or not files:
        msg = (r.stderr.strip().splitlines() or ["?"])[-1]
        hint = ""
        if "403" in msg:
            hint = (" — yt-dlp büyük ihtimalle eski: scripts/doctor.py'yi yeniden çalıştır (günceller) ve tekrar dene. "
                    "Yine olmazsa MCP yolundaki izleme araçlarına geç (references/mcp-yolu.md §3); engeli aşmaya çalışma.")
        elif "Sign in" in msg or "bot" in msg.lower():
            hint = " — platform bu ortamı engelliyor; MCP yoluna geç (references/mcp-yolu.md §3), engeli aşmaya çalışma."
        sys.exit(f"HATA: video penceresi indirilemedi: {msg}{hint}")
    # İndirilen parça 0'dan başlar; zamanları orijinal videoya göre raporlamak için ofset
    return os.path.join(outdir, files[0]), 0.0


def probe_duration(path):
    d = _env.media_duration(path)
    if d is None:
        sys.exit("HATA: video süresi okunamadı (dosya bozuk olabilir).")
    return d


def detect_cuts(path, seek, length):
    r = run([_env.ffmpeg_path(), "-hide_banner", "-nostats", "-ss", str(seek), "-t", str(length), "-i", path,
             "-an", "-vf", f"select=gt(scene\\,{SCENE_THRESHOLD}),showinfo", "-f", "null", "-"])
    return [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def visual_changes(path, seek, length, fps=4, bits=26, min_gap=1.5):
    """Yumuşak geçişli (crossfade, kamera hareketli) kurgu için ikinci ölçü: saniyede 4 küçük kare,
    9x8 fark hash'i; bir önceki görselden >26 bit uzaklaşan ve ≥1,5 sn arayla gelen her kare yeni görsel
    sayılır. Sahne eşiği (0.3) bu kurguda 0 kesim gösterebilir (2026-11-12, belgesel testi)."""
    r = subprocess.run([_env.ffmpeg_path(), "-v", "error", "-ss", str(seek), "-t", str(length), "-i", path,
                        "-an", "-vf", f"fps={fps},scale=9:8,format=gray", "-f", "rawvideo", "-"],
                       capture_output=True)
    px = r.stdout
    frames = [px[i:i + 72] for i in range(0, len(px) - 71, 72)]
    if not frames:
        return []
    def hb(f):
        return [f[row * 9 + c] > f[row * 9 + c + 1] for row in range(8) for c in range(8)]
    ref, last, out = hb(frames[0]), 0.0, []
    for i, f in enumerate(frames[1:], 1):
        t = i / fps
        h = hb(f)
        if sum(x != y for x, y in zip(ref, h)) > bits and t - last >= min_gap:
            out.append(round(t, 2))
            ref, last = h, t
    return out


def frame_budget(length):
    # watch-skill'in "odaklı pencere" kademeleri: kısa pencere = saniye başına daha çok kare
    if length <= 15:
        return 10
    if length <= 45:
        return 16
    if length <= 120:
        return 24
    return 32


def dhash(path):
    """9x8 gri piksel → 64 bitlik fark hash'i (ffmpeg ile, Pillow gerekmez)."""
    r = subprocess.run([_env.ffmpeg_path(), "-v", "error", "-i", path, "-vf", "scale=9:8,format=gray",
                        "-f", "rawvideo", "-"], capture_output=True)
    px = r.stdout
    if len(px) < 72:
        return None
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    return bits


def grab(path, t, out):
    subprocess.run([_env.ffmpeg_path(), "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1",
                    "-vf", "scale=640:-2", "-q:v", "4", out], capture_output=True)
    return os.path.exists(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("--start", type=float, default=0)
    p.add_argument("--end", type=float, default=40)
    p.add_argument("--max-frames", type=int)
    p.add_argument("--outdir", default="izleme")
    p.add_argument("--cuts-only", action="store_true", help="kare çıkarma, yalnız kesim temposu")
    p.add_argument("--keep", action="store_true", help="indirilen video parçasını silme")
    a = p.parse_args()
    if a.end <= a.start:
        sys.exit("HATA: --end, --start'tan büyük olmalı.")
    _env.ffmpeg_path()
    os.makedirs(a.outdir, exist_ok=True)

    path, seek = acquire(a.src, a.start, a.end, a.outdir)
    length = min(a.end - a.start, probe_duration(path) - seek)
    cuts_rel = detect_cuts(path, seek, length)
    cuts = [round(a.start + c, 2) for c in cuts_rel]
    shots = [0.0] + cuts_rel + [length]
    gaps = [b - x for x, b in zip(shots, shots[1:]) if b - x > 0]
    result = {
        "source": a.src,
        "window": [a.start, round(a.start + length, 2)],
        "cuts": cuts,
        "cut_count": len(cuts),
        "cuts_per_min": round(len(cuts) / (length / 60), 1) if length else None,
        "avg_shot_s": round(sum(gaps) / len(gaps), 2) if gaps else None,
        "longest_shot_s": round(max(gaps), 2) if gaps else None,
        "scene_threshold": SCENE_THRESHOLD,
    }
    vis = visual_changes(path, seek, length)
    result["visual_changes_per_min"] = round(len(vis) / (length / 60), 1) if length else None
    if length and result["visual_changes_per_min"] and result["cuts_per_min"] < 0.5 * result["visual_changes_per_min"]:
        result["soft_transitions"] = True
        result["note"] = ("Sert kesim az ama görsel değişim çok: kurgu yumuşak geçişli/kamera hareketli. "
                          "Tempo ölçüsü olarak visual_changes_per_min'i kullan, temas sayfasından doğrula.")

    if not a.cuts_only:
        budget = a.max_frames or frame_budget(length)
        # Aday zamanlar: her kesimin hemen sonrası + pencere başı, sonra bütçeye kadar düzenli doldurma
        cand = [(0.1, "pencere-basi")] + [(c + CUT_OFFSET, "kesim") for c in cuts_rel if c + CUT_OFFSET < length]
        if len(cand) < budget:
            n = budget - len(cand)
            cand += [(length * (i + 0.5) / n, "duzenli") for i in range(n)]
        cand = sorted(cand)[: budget * 2]
        fdir = os.path.join(a.outdir, "kareler")
        os.makedirs(fdir, exist_ok=True)
        kept, hashes = [], []
        for t, why in cand:
            if len(kept) >= budget:
                break
            abs_t = a.start + t
            out = os.path.join(fdir, f"t{int(abs_t // 60):02d}m{abs_t % 60:05.2f}s.jpg")
            if not grab(path, seek + t, out):
                continue
            h = dhash(out)
            if h is not None and any(bin(h ^ x).count("1") <= DHASH_MAX_DIST for x in hashes):
                os.remove(out)  # neredeyse aynı kare: bağlam bütçesini boşa harcamasın
                continue
            hashes.append(h if h is not None else 0)
            kept.append({"t": round(abs_t, 2), "path": out, "reason": why})
        kept.sort(key=lambda f: f["t"])
        result["frames"] = kept
        # Temas sayfası: tüm kareler tek görselde, zaman sırasıyla (soldan sağa, yukarıdan aşağı)
        if kept:
            cols = 4
            rows = (len(kept) + cols - 1) // cols
            sheet = os.path.join(a.outdir, "temas-sayfasi.jpg")
            inputs = []
            for f in kept:
                inputs += ["-i", f["path"]]
            pads = cols * rows - len(kept)
            filt = "".join(f"[{i}:v]scale=320:-2[v{i}];" for i in range(len(kept)))
            chain = "".join(f"[v{i}]" for i in range(len(kept)))
            filt += f"{chain}concat=n={len(kept)}:v=1:a=0,tile={cols}x{rows}:padding=4"
            r = subprocess.run([_env.ffmpeg_path(), "-v", "error", "-y", *inputs, "-filter_complex", filt,
                                "-frames:v", "1", sheet], capture_output=True, text=True)
            if r.returncode == 0 and pads >= 0 and os.path.exists(sheet):
                result["contact_sheet"] = sheet
                result["contact_sheet_order"] = [f["t"] for f in kept]
        result["next"] = ("Kareleri tek mesajda paralel Read ile aç (ya da önce temas sayfasını). "
                          "Gözlemi aynı penceredeki transkript satırlarıyla karşılaştır; uyuşmuyorsa yorum yapma.")

    # İndirilen video parçasını sil: analiz için kareler ve ölçüler yeter; içeriği saklamamak
    # hem disk hem telif/kullanım şartları açısından doğru olan. Yerel dosyalara dokunulmaz.
    if not a.keep and os.path.basename(path).startswith("pencere.") and os.path.dirname(os.path.abspath(path)) == os.path.abspath(a.outdir):
        os.remove(path)
    with open(os.path.join(a.outdir, "watch.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
