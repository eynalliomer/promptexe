#!/usr/bin/env python3
"""Ortamı kontrol eder ve eksikleri KENDİSİ kurar — kullanıcıya iş bırakmaz.

Kullanım:
    python3 doctor.py [<referans_linki>] [--asr]

Yaptıkları:
  1. Skill-yerel sanal ortam (~/.cache/promptexe/venv; PROMPTEXE_HOME ile değişir) yoksa kurar.
  2. yt-dlp'yi kurar; 30 günden eskiyse günceller (eski yt-dlp YouTube'da 403 alır).
  3. ffmpeg sistemde yoksa taşınabilir ffmpeg'i (imageio-ffmpeg) kurar.
  4. --asr verilirse sesten yazıya için faster-whisper'ı kurar (büyük; yalnız gerektiğinde).
  5. Link verilirse ona erişimi dener (yalnız bilgi çeker, video indirmez).
Global hiçbir şey kurmaz. Çıktı: tek satır JSON — mode, python, yt-dlp sürümü, ffmpeg, erişim.

mode:
  "tam"      → her şey yerelde çalışır (kanal, transkript, izleme, ölçüm)
  "erisimsiz"→ araçlar hazır ama platforma erişilemiyor (ör. sunucu IP'si engelli) →
               bağlı analitik aracına (MCP) geç
  "kurulamadi" → paket kurulamadı (ağ yok) → bağlı analitik aracına geç
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _env  # noqa: E402

YTDLP_MAX_AGE_DAYS = 30  # YouTube çıkarıcısı sık bozulur; bir aydan eski sürüm risklidir


def sh(cmd, timeout=900):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def find_base_python():
    """venv için python: tercihen ≥3.10 (güncel yt-dlp ister); yoksa ≥3.9 (ffmpeg paketi için yeter,
    yt-dlp o durumda resmi tek dosyalık sürümden gelir)."""
    cands = [sys.executable] + [shutil.which(n) for n in ("python3.13", "python3.12", "python3.11", "python3.10", "python3")]
    fallback = None
    for c in cands:
        if not c:
            continue
        # Sayısal karşılaştırma: metin olarak "(3, 9)" >= "(3, 10)" DOĞRU çıkar (eski hata)
        r = sh([c, "-c", "import sys;print(sys.version_info[0]*100+sys.version_info[1])"])
        v = int(r.stdout.strip() or 0)
        if v >= 310:
            return c
        if v >= 309 and not fallback:
            fallback = c
    return fallback


def py_version(py):
    r = sh([py, "-c", "import sys;print(sys.version_info[0]*100+sys.version_info[1])"])
    return int(r.stdout.strip() or 0)


def ytdlp_age(ver):
    m = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", ver or "")
    if not m:
        return None
    return (datetime.date.today() - datetime.date(*map(int, m.groups()))).days


def download_ytdlp_binary():
    """yt-dlp'nin resmi GitHub sürüm dosyası (python gerektirmez) → PROMPTEXE_HOME/bin/yt-dlp."""
    import platform
    import urllib.request
    name = {"Darwin": "yt-dlp_macos", "Linux": "yt-dlp_linux", "Windows": "yt-dlp.exe"}.get(platform.system())
    if platform.system() == "Linux" and platform.machine() in ("aarch64", "arm64"):
        name = "yt-dlp_linux_aarch64"
    if not name:
        return None
    url = f"https://github.com/yt-dlp/yt-dlp/releases/latest/download/{name}"
    dest = _env.bin_ytdlp_path()
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        urllib.request.urlretrieve(url, dest + ".part")
        os.replace(dest + ".part", dest)
        os.chmod(dest, 0o755)
    except Exception:
        return None
    r = sh([dest, "--version"])
    return r.stdout.strip() if r.returncode == 0 else None


def pip(py, *pkgs):
    return sh([py, "-m", "pip", "install", "-q", "--disable-pip-version-check", "-U", *pkgs], timeout=1800)


def main():
    url = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    want_asr = "--asr" in sys.argv
    report = {"actions": []}
    home = _env.home()
    os.makedirs(home, exist_ok=True)

    py = _env.venv_python()
    if py and py_version(py) < 310:
        base = find_base_python()
        if base and py_version(base) >= 310:
            # Eski python'lu ortam güncel yt-dlp alamıyor → yavaş tek-dosya sürümüne düşüyordu.
            # venv'in kendi --clear seçeneğiyle aynı klasörde yeniden kur (yalnız skill ortamı).
            r = sh([base, "-m", "venv", "--clear", os.path.join(home, "venv")])
            if r.returncode == 0:
                report["actions"].append("sanal ortam yeni python ile yeniden kuruldu")
                py = _env.venv_python()
    if not py:
        base = find_base_python()
        if not base:
            print(json.dumps({"mode": "kurulamadi", "error": "Python 3.10+ bulunamadı"}, ensure_ascii=False))
            return
        r = sh([base, "-m", "venv", os.path.join(home, "venv")])
        py = _env.venv_python()
        if r.returncode != 0 or not py:
            print(json.dumps({"mode": "kurulamadi", "error": "sanal ortam kurulamadı: " + r.stderr[-200:]}, ensure_ascii=False))
            return
        report["actions"].append("sanal ortam kuruldu")

    # yt-dlp: güncel (≤30 gün) olanların EN HIZLISI seçilir ve ytdlp.json'a yazılır.
    # Sıra: venv modülü (~0 sn açılış) → sistemdeki yt-dlp (~1 sn) → resmi tek dosya (~10 sn açılış:
    # macOS her çalıştırmada kendini açıp tarıyor; yalnız başka yol yoksa).
    def candidates():
        out = [("venv", [py, "-m", "yt_dlp"])]
        sysy = shutil.which("yt-dlp")
        if sysy:
            out.append(("sistem", [sysy]))
        b = _env.bin_ytdlp_path()
        if os.path.exists(b):
            out.append(("binary", [b]))
        return out

    def pick():
        for kind, cmd in candidates():
            r = sh(cmd + ["--version"])
            v = r.stdout.strip() if r.returncode == 0 else None
            a_ = ytdlp_age(v)
            if v and a_ is not None and a_ <= YTDLP_MAX_AGE_DAYS:
                return v, kind, cmd, a_
        return None, None, None, None

    ver, kind, cmd, age = pick()
    if not ver:
        if py_version(py) >= 310 and pip(py, "yt-dlp").returncode == 0:
            report["actions"].append("yt-dlp kuruldu/güncellendi (pip)")
        ver, kind, cmd, age = pick()
    if not ver:
        bv = download_ytdlp_binary()
        if bv:
            report["actions"].append("yt-dlp resmi tek dosya sürümü indirildi (yavaş açılış)")
        ver, kind, cmd, age = pick()
    if not ver:
        # Güncel hiçbiri yok: eski de olsa çalışan ilkini kullan, uyar
        for k_, c_ in candidates():
            r = sh(c_ + ["--version"])
            if r.returncode == 0:
                ver, kind, cmd, age = r.stdout.strip(), k_, c_, ytdlp_age(r.stdout.strip())
                break
    if ver:
        with open(os.path.join(home, "ytdlp.json"), "w", encoding="utf-8") as f:
            json.dump({"cmd": cmd, "kind": kind, "version": ver}, f)
        if kind == "binary":
            report.setdefault("warnings", []).append("yt-dlp tek dosya sürümüyle çalışıyor: her çağrı ~10 sn açılış — Python 3.10+ kurulursa hızlanır")
    if not ver:
        print(json.dumps({"mode": "kurulamadi", "error": "yt-dlp kurulamadı (ağ yok?)"}, ensure_ascii=False))
        return
    if age is not None and age > YTDLP_MAX_AGE_DAYS:
        report.setdefault("warnings", []).append(f"yt-dlp {age} günlük ve güncellenemedi (403 riski)")
    report["ytdlp"] = f"{ver} ({kind})"

    # ffmpeg: sistemde yoksa taşınabilir sürüm
    if not shutil.which("ffmpeg"):
        if sh([py, "-c", "import imageio_ffmpeg"]).returncode != 0:
            if pip(py, "imageio-ffmpeg").returncode == 0:
                report["actions"].append("taşınabilir ffmpeg kuruldu")
        r = sh([py, "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"])
        report["ffmpeg"] = r.stdout.strip() or None
    else:
        report["ffmpeg"] = shutil.which("ffmpeg")

    if want_asr and sh([py, "-c", "import faster_whisper"]).returncode != 0:
        r = pip(py, "faster-whisper")
        report["actions"].append("faster-whisper kuruldu" if r.returncode == 0 else "faster-whisper KURULAMADI")
    report["asr"] = sh([py, "-c", "import faster_whisper"]).returncode == 0

    report["python"] = py
    mode = "tam" if report.get("ffmpeg") else "kurulamadi"
    if url and mode == "tam":
        yt = cmd
        r = sh(yt + ["--no-warnings", "--skip-download", "--no-playlist",
                "--playlist-end", "1", "--print", "%(title)s", "--", url], timeout=120)
        if r.returncode == 0 and r.stdout.strip():
            report["access"] = "ok"
        else:
            msg = (r.stderr.strip().splitlines() or ["?"])[-1]
            report["access"] = "engelli: " + msg[:160]
            mode = "erisimsiz"
    report["mode"] = mode
    report["next"] = {
        "tam": f"Tüm script'leri bu python ile çalıştır: {py} scripts/<script>.py …",
        "erisimsiz": "Platform bu ortamdan erişilemiyor: bağlı analitik aracını (MCP) kullan. Engeli aşmaya çalışma.",
        "kurulamadi": "Paket kurulamadı: bağlı analitik aracını (MCP) kullan.",
    }[mode]
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
