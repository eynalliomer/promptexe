#!/usr/bin/env python3
"""Kanal/profil video listesini yt-dlp ile çeker ve sekme bazında outlier skorlarını hesaplar.

Kullanım:
    python3 fetch_channel.py <kanal_veya_profil_linki> [--limit 30] [--out kanal.json]

Kanal analitiği aracı (ör. Nexlev) bağlı DEĞİLSE kullanılır. YouTube kanalları, TikTok
profilleri ve (çoğu zaman çerez isteyen) Instagram profilleriyle çalışır.

YouTube kanal kökü sekmeleri (Videos, Shorts, Live) ayrı listeler olarak döner; uzun video ile
Shorts'un izlenme ölçeği çok farklı olduğu için özet HER SEKME İÇİN AYRI hesaplanır.
Hızlı listede izlenme/tarih eksikse o sekme video başına zenginleştirilir (~1,5-2 sn/video).

Çıktı (JSON): kanal adı/ID, sekmeler -> video listesi (id, başlık, izlenme, süre, tarih,
outlier_score = izlenme / sekme medyanı) ve özet (medyan, outlier'lar, en iyi 4, en zayıf 3).
"""
import argparse
import datetime
import json
import statistics
import subprocess
import sys
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import _env  # noqa: E402
_env.ensure_venv_python()

# Medyanın 3 katı: "outlier" için yaygın eşik; 2x küçük kanallarda gürültülü,
# 5x ise çoğu kanalda hiçbir şey yakalamıyor.
OUTLIER_RATIO = 3.0
SERIES_MIN = 3  # aynı numaralı başlık kalıbını taşıyan ≥3 video = ayrı bir seri (ör. "… - 9. Gün Özeti")


def _series_keys(title):
    """Numaralı seri kalıbı: rakamlar '#'e, noktalama boşluğa indirgenir; baştaki 4 ya da sondaki
    3 kelimede '#' varsa o parça seri anahtarıdır ("artemis ii # gün", "episode #")."""
    import re
    t = re.sub(r"\d+", "#", (title or "").lower())
    toks = re.sub(r"[^\w#]+", " ", t).split()
    keys = []
    if "#" in toks[:4]:
        keys.append("P:" + " ".join(toks[:4]))
    if "#" in toks[-3:]:
        keys.append("S:" + " ".join(toks[-3:]))
    return keys


def find_series(rows):
    """{video_id: seri_anahtarı} — yalnız ≥SERIES_MIN üyeli numaralı kalıplar."""
    from collections import defaultdict
    groups = defaultdict(list)
    for x in rows:
        for k in _series_keys(x.get("title")):
            groups[k].append(x["id"])
    out = {}
    for k, ids in groups.items():
        if len(ids) >= SERIES_MIN:
            for i in ids:
                out.setdefault(i, k[2:])
    return out


def ytdlp(args, timeout=900):
    try:
        r = subprocess.run(_env.ytdlp_base() + ["--no-warnings", "--ignore-errors"] + args,
                           capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        sys.exit("HATA: yt-dlp yok. Önce scripts/doctor.py çalıştır (kendisi kurar).")
    except subprocess.TimeoutExpired:
        sys.exit("HATA: yt-dlp zaman aşımı. --limit değerini düşür.")
    return r


def fail(r, url):
    msg = (r.stderr.strip().splitlines() or ["bilinmeyen hata"])[-1]
    hint = ""
    if "instagram" in url and any(k in msg.lower() for k in ("login", "cookie", "rate")):
        hint = (" — Instagram giriş istiyor: --cookies-from-browser chrome ekleyerek dene "
                "ya da kullanıcıdan profil ekran görüntüsü/izlenme listesi iste.")
    elif "Sign in to confirm" in msg or "bot" in msg.lower():
        hint = " — YouTube bu ortamı engelliyor. MCP yoluna geç (references/mcp-yolu.md); engeli aşmaya çalışma."
    sys.exit(f"HATA: yt-dlp başarısız: {msg}{hint}")


def entry_row(e):
    return {
        "id": e.get("id"),
        "title": e.get("title"),
        "url": e.get("url") if str(e.get("url", "")).startswith("http") else e.get("webpage_url"),
        "views": e.get("view_count"),
        "duration_s": e.get("duration"),
        "upload_date": e.get("upload_date"),
    }


ENRICH_WORKERS = 6  # eşzamanlı yt-dlp süreci; daha fazlası YouTube'da 429 (Too Many Requests) riskini artırır


def enrich(ids, shorts=False):
    """Video başına izlenme/süre/tarih — hızlı listede eksik olduğunda. Videolar PARALEL çekilir
    (yt-dlp bir listeyi sırayla işler: 30 video ≈ 50 sn; 6 paralel süreçle ≈ 10 sn)."""
    from concurrent.futures import ThreadPoolExecutor
    base = "https://www.youtube.com/shorts/" if shorts else "https://www.youtube.com/watch?v="

    def one(vid):
        r = ytdlp(["--skip-download", "--no-playlist",
                   "--print", "%(id)s\t%(view_count)s\t%(duration)s\t%(upload_date)s", base + vid], timeout=180)
        parts = (r.stdout.strip().splitlines() or [""])[-1].split("\t")
        if len(parts) != 4:
            return vid, {}
        _, v, d, u = parts
        return vid, {"views": int(v) if v.isdigit() else None,
                     "duration_s": float(d) if d not in ("NA", "None", "") else None,
                     "upload_date": u if u.isdigit() else None}

    with ThreadPoolExecutor(max_workers=ENRICH_WORKERS) as ex:
        return dict(ex.map(one, ids))


def summarize(rows):
    viewed = [x for x in rows if isinstance(x["views"], int)]
    s = {"count": len(rows), "with_views": len(viewed)}
    if not viewed:
        s["note"] = "İzlenme verisi yok."
        return s
    med = statistics.median(x["views"] for x in viewed)
    today = datetime.date.today()
    for x in viewed:
        x["outlier_score"] = round(x["views"] / med, 2) if med else None
        if x.get("upload_date"):
            age = (today - datetime.datetime.strptime(x["upload_date"], "%Y%m%d").date()).days
            x["age_days"] = age
            # Yeni videolar henüz birikmedi: 14 günden genç videoyu "zayıf" saymamak için işaretle
            x["too_new"] = age < 14
            x["views_per_day"] = round(x["views"] / max(age, 1))
    ranked = sorted(viewed, key=lambda x: x["views"], reverse=True)
    # Aynı format: süresi medyanın 0,5–2 katı (müzik klibi, fragman gibi farklı formatlar kıyası bozar)
    durs_v = [x["duration_s"] for x in viewed if x.get("duration_s")]
    med_d = statistics.median(durs_v) if durs_v else None
    same = [x for x in viewed if not med_d or not x.get("duration_s") or 0.5 * med_d <= x["duration_s"] <= 2 * med_d]
    # Olgun kanal: 14 günü geçmiş ≥3 video varsa toplam izlenme adil ölçüdür. Genç kanalda (hepsi
    # yeni) toplam izlenme yaşla şişer → günlük izlenmeyle sırala (ilk 3 günün oynaklığı hariç).
    matured = [x for x in same if (x.get("age_days") or 0) >= 14]
    if len(matured) >= 3 or not any(x.get("age_days") is not None for x in same):
        metric, pool = "views", (matured if len(matured) >= 3 else same)
        key = lambda x: x["views"]
    else:
        metric, pool = "views_per_day", [x for x in same if (x.get("age_days") or 0) >= 3] or same
        key = lambda x: x.get("views_per_day") or 0
    perf = sorted(pool, key=key, reverse=True)
    # Numaralı seri (günlük özet, bölüm) kanalın ana formatı değilse zayıf aday olamaz: kaybeden
    # videoyu başka bir formatla kıyaslamak "neden tutmadı" sorusuna yanlış cevap verir.
    series = find_series(viewed)
    top_ids = {x["id"] for x in perf[:4]}
    main_series = {series[i] for i in top_ids if i in series}
    side = {i for i, k in series.items() if k not in main_series}
    perf_w = [x for x in perf if x["id"] not in side] or perf
    s.update({
        "median_views": med,
        "outliers": [x["id"] for x in ranked if (x.get("outlier_score") or 0) >= OUTLIER_RATIO],
        "metric": metric,
        "top": [x["id"] for x in perf[:4]],
        "weakest": [x["id"] for x in perf_w[4:]][-3:] if len(perf_w) > 4 else [x["id"] for x in perf_w[-1:]],
        # zayıftan güçlüye ek adaylar: analyze_reference ses dili tutmazsa sıradakine geçer
        "weak_candidates": [x["id"] for x in perf_w[4:]][::-1][:8],
        "format_disi": [x["id"] for x in viewed if x not in same],
        "seri_disi": sorted(side),
        "seriler": sorted({series[i] for i in side}),
    })
    dates = sorted(x["upload_date"] for x in rows if x.get("upload_date"))
    if dates:
        s["date_range"] = [dates[0], dates[-1]]
    durs = [x["duration_s"] for x in rows if x.get("duration_s")]
    if durs:
        s["median_duration_s"] = statistics.median(durs)
    return s


def main():
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--limit", type=int, default=30, help="sekme başına video sayısı")
    p.add_argument("--no-enrich", action="store_true", help="eksik izlenmeleri tamamlama (hızlı)")
    p.add_argument("--tab", help="yalnız bu sekmeyi zenginleştir (videos/shorts/live); diğerleri hızlı listeyle özetlenir")
    p.add_argument("--out")
    a = p.parse_args()

    r = ytdlp(["--flat-playlist", "--dump-single-json", "--playlist-end", str(a.limit), a.url])
    if not r.stdout.strip():
        fail(r, a.url)
    info = json.loads(r.stdout)

    tabs = {}
    entries = info.get("entries") or []
    if entries and all(e and e.get("_type") == "playlist" for e in entries):
        for e in entries:
            name = (e.get("title") or "tab").split(" - ")[-1].lower()
            tabs[name] = (e.get("webpage_url"), [entry_row(x) for x in e.get("entries") or [] if x])
    else:
        tabs["videos"] = (a.url, [entry_row(x) for x in entries if x])

    result = {
        "channel": info.get("channel") or info.get("uploader") or info.get("title"),
        "channel_id": info.get("channel_id") or info.get("id"),
        "source_url": a.url,
        "tabs": {},
    }
    for name, (tab_url, rows) in tabs.items():
        # İzlenme ya da yükleme tarihi eksikse zenginleştir: tarih olmadan yaş, günlük izlenme ve
        # "yeni video" ayrımı yapılamaz (genç kanalda zayıf video seçimi yanlış çıkar)
        missing = sum(1 for x in rows if x["views"] is None or not x.get("upload_date"))
        wanted = not a.tab or name == a.tab or (a.tab == "videos" and len(tabs) == 1)
        if rows and missing > len(rows) / 2 and wanted and not a.no_enrich:
            extra = enrich([x["id"] for x in rows if x.get("id")], shorts=(name == "shorts"))
            for x in rows:
                for k, v in (extra.get(x["id"]) or {}).items():
                    if x.get(k) is None:
                        x[k] = v
        result["tabs"][name] = {"summary": summarize(rows), "videos": rows}

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Yazıldı: {a.out}")
        for name, t in result["tabs"].items():
            s = t["summary"]
            print(f"  {name}: {s['count']} video, izlenmeli {s['with_views']}, medyan {s.get('median_views')}, "
                  f"outlier {len(s.get('outliers', []))}")
    else:
        print(text)


if __name__ == "__main__":
    main()
