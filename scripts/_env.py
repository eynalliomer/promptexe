"""Ortak araç bulucu: tüm script'ler yt-dlp ve ffmpeg'i buradan bulur.

Öncelik: doctor.py'nin kurduğu skill-yerel ortam (güncel yt-dlp + taşınabilir ffmpeg) →
sistemdeki araçlar. Böylece kullanıcının makinesine global hiçbir şey kurulmaz ve
eski bir sistem yt-dlp'si (YouTube'da 403'ün en sık sebebi) devreye girmez.
"""
import importlib.util
import os
import shutil
import subprocess
import sys


def home():
    return os.environ.get("PROMPTEXE_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "promptexe")


def venv_python():
    bin_dir = "Scripts" if os.name == "nt" else "bin"
    p = os.path.join(home(), "venv", bin_dir, "python.exe" if os.name == "nt" else "python")
    return p if os.path.exists(p) else None


def ensure_venv_python():
    """Script sistem python'uyla çağrıldıysa ve skill ortamı varsa, kendini oradan yeniden çalıştır."""
    vp = venv_python()
    venv_dir = os.path.join(home(), "venv")
    # venv python'u taban python'a sembolik bağdır; realpath karşılaştırması işe yaramaz → prefix'e bak
    inside = os.path.realpath(sys.prefix) == os.path.realpath(venv_dir)
    if vp and not inside and not os.environ.get("PROMPTEXE_REEXEC"):
        os.environ["PROMPTEXE_REEXEC"] = "1"
        os.execv(vp, [vp] + sys.argv)


def bin_ytdlp_path():
    return os.path.join(home(), "bin", "yt-dlp.exe" if os.name == "nt" else "yt-dlp")


def ytdlp_cmd():
    # doctor.py en hızlı güncel yt-dlp'yi seçip ytdlp.json'a yazar; önce ona uy
    try:
        import json as _json
        rec = _json.load(open(os.path.join(home(), "ytdlp.json"), encoding="utf-8"))
        cmd = rec.get("cmd") or []
        if cmd and (os.path.exists(cmd[0]) or shutil.which(cmd[0])):
            return list(cmd)
    except (OSError, ValueError):
        pass
    if importlib.util.find_spec("yt_dlp"):
        return [sys.executable, "-m", "yt_dlp"]
    if shutil.which("yt-dlp"):
        return ["yt-dlp"]
    b = bin_ytdlp_path()
    if os.path.exists(b):
        return [b]
    sys.exit("HATA: yt-dlp yok. Önce `python3 scripts/doctor.py` çalıştır (kendisi kurar).")


def ffmpeg_path(required=True):
    p = shutil.which("ffmpeg")
    if p:
        return p
    if importlib.util.find_spec("imageio_ffmpeg"):
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    if required:
        sys.exit("HATA: ffmpeg yok. Önce `python3 scripts/doctor.py` çalıştır (kendisi kurar).")
    return None


def ytdlp_base():
    """yt-dlp komutu + (gerekirse) taşınabilir ffmpeg konumu."""
    cmd = ytdlp_cmd()
    ff = ffmpeg_path(required=False)
    if ff and not shutil.which("ffmpeg"):
        cmd += ["--ffmpeg-location", ff]
    return cmd


def media_duration(path):
    """ffprobe olmadan süre: ffmpeg -i çıktısındaki 'Duration: HH:MM:SS.xx'."""
    r = subprocess.run([ffmpeg_path(), "-hide_banner", "-i", path], capture_output=True, text=True)
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    if not m:
        return None
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)
