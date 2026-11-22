#!/usr/bin/env python3
"""Piyasa konu havuzu: nişte TUTMUŞ benzer videoları bulur — konu seçeneğini kanıta dayandırmak için.

Kullanım:
    python3 market_topics.py "medieval peasant vlog" "day in the life 1300s" [--exclude "Kanal Adı"]
                             [--per-query 25] [--top 15] [--out piyasa.json]

Her sorgu iki kez aranır: alaka sıralı ve izlenme sıralı (YouTube'un kendi sıralaması). Sonuçlar
birleştirilir, referans kanal(lar) çıkarılır, en çok izlenen --top video için yükleme tarihi
çekilir (günlük izlenme = "şu an da tutuyor mu" göstergesi). Çıktı: JSON + kopyalanabilir tablo.

Claude'un işi: sorguları analizden türetmek (referansın konusu + kullanıcının nişi, 3-5 sorgu,
gerekirse hedef dilde), sonra her satırı kullanıcının konusuna UYARLAMAK — başlığı kopyalamak değil.
Analitik MCP aracı (ör. Nexlev) varsa onun arama/outlier araçları daha zengin veri verir:
references/mcp-yolu.md §5.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import _env  # noqa: E402
_env.ensure_venv_python()

import argparse
import datetime
import json
import subprocess
import sys
import urllib.parse

SORT_BY_VIEWS = "CAM%3D"  # YouTube arama parametresi: izlenmeye göre sırala
SHORTS_MAX_S = 180         # YouTube Shorts üst sınırı (3 dk)
# Format dışı gürültü: müzik (klip, "- Topic" otomatik kanalları, plak şirketleri) ve marka reklamı.
# 3 kanal testinde Türkçe sorgular müzik klibi, İngilizce sorgular marka filmi döndürdü (gözlem 0017 #7).
NOISE_CHANNEL = (" - topic", "vevo", "müzik", "muzik", "music", "records", "prodüksiyon")
NOISE_TITLE = ("official video", "official music video", "official audio", "official lyric", "lyric video",
               "lyrics", "(audio)", "music video", "klip", "remix", "brand film", "commercial", "reklam filmi")


def search(url, limit):
    r = subprocess.run(_env.ytdlp_base() + ["--no-warnings", "--flat-playlist", "--dump-single-json",
                                             "--playlist-end", str(limit), url],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not r.stdout.strip():
        return []
    return [e for e in (json.loads(r.stdout).get("entries") or []) if e and e.get("id")]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("queries", nargs="+")
    p.add_argument("--exclude", action="append", default=[], help="çıkarılacak kanal adı (referans)")
    p.add_argument("--per-query", type=int, default=25)
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--min-views", type=int, default=10000)
    p.add_argument("--exclude-word", action="append", default=[],
                   help="başlığında bu kelime geçenleri at (ör. minecraft, reaction) — formata uymayan gürültü")
    p.add_argument("--shorts", action="store_true",
                   help=f"Shorts nişi: sorgulara #shorts ekler ve yalnız ≤{SHORTS_MAX_S} sn videoları tutar")
    p.add_argument("--min-duration", type=float, help="sn; uzun formatta referans medyan süresinin ~yarısı")
    p.add_argument("--max-duration", type=float, help="sn")
    p.add_argument("--lang", help="yalnız bu ses dilindeki videolar (ör. en, tr); dili bilinmeyen tutulur")
    p.add_argument("--keep-noise", action="store_true", help="müzik/reklam filtresini kapat")
    p.add_argument("--out")
    a = p.parse_args()
    if a.shorts:
        a.queries = [q if "#shorts" in q.lower() else q + " #shorts" for q in a.queries]
        a.max_duration = min(a.max_duration or SHORTS_MAX_S, SHORTS_MAX_S)
    excl = {x.lower() for x in a.exclude}

    from concurrent.futures import ThreadPoolExecutor
    jobs = []
    for q in a.queries:
        qs = urllib.parse.quote(q)
        jobs += [(q, f"ytsearch{a.per_query}:{q}"),
                 (q, f"https://www.youtube.com/results?search_query={qs}&sp={SORT_BY_VIEWS}")]
    # Aramalar paralel (sorgu × 2 sıralama); sıralı çalışınca her biri ~10-20 sn bekletiyordu
    with ThreadPoolExecutor(max_workers=4) as ex:
        found = list(ex.map(lambda j: (j[0], search(j[1], a.per_query)), jobs))
    seen, dropped = {}, {"sure": 0, "gurultu": 0, "dil": 0}

    def noisy(ch, title_l):
        c = ch.lower()
        return any(w in c for w in NOISE_CHANNEL) or any(w in title_l for w in NOISE_TITLE)

    for q, entries in found:
        if True:
            for e in entries:
                ch = (e.get("channel") or e.get("uploader") or "")
                v = e.get("view_count")
                title_l = (e.get("title") or "").lower()
                if (ch.lower() in excl or not isinstance(v, int) or v < a.min_views
                        or any(w.lower() in title_l for w in a.exclude_word)):
                    continue
                d = e.get("duration")
                if isinstance(d, (int, float)) and ((a.min_duration and d < a.min_duration)
                                                    or (a.max_duration and d > a.max_duration)):
                    dropped["sure"] += 1
                    continue
                if not a.keep_noise and noisy(ch, title_l):
                    dropped["gurultu"] += 1
                    continue
                if e["id"] not in seen:
                    seen[e["id"]] = {"id": e["id"], "baslik": e.get("title"), "kanal": ch, "izlenme": v,
                                     "sure_sn": e.get("duration"), "sorgu": q,
                                     "url": f"https://www.youtube.com/watch?v={e['id']}"}
    # Dil filtresi detay çağrısı ister: adaylar --top'un 2 katı alınır, elenen yerine sıradaki girer
    rows = sorted(seen.values(), key=lambda r: -r["izlenme"])[: a.top * (2 if a.lang else 1)]
    if not rows:
        sys.exit("HATA: arama sonuç vermedi (erişim engeli olabilir) — MCP arama araçlarına geç (mcp-yolu.md §5).")

    # Yükleme tarihi yalnız ilk --top için (video başına ~1,5 sn): eski viral mi, güncel mi?
    def date_of(vid):
        r = subprocess.run(_env.ytdlp_base() + ["--no-warnings", "--skip-download", "--no-playlist",
                                                 "--print", "%(upload_date)s\t%(language)s",
                                                 f"https://www.youtube.com/watch?v={vid}"],
                           capture_output=True, text=True, timeout=180)
        parts = ((r.stdout.strip().splitlines() or [""])[-1] + "\t").split("\t")
        lang = parts[1].strip().split("-")[0].lower()
        return vid, (parts[0].strip(), None if lang in ("", "na", "none") else lang)

    with ThreadPoolExecutor(max_workers=6) as ex:  # 6: 429 riskine karşı sınır
        details = dict(ex.map(date_of, [r["id"] for r in rows]))
    if a.lang:
        want = a.lang.split("-")[0].lower()
        keep = [r for r in rows if details.get(r["id"], ("", None))[1] in (None, want)]
        dropped["dil"] = len(rows) - len(keep)
        rows = keep[: a.top]
    today = datetime.date.today()
    for row in rows:
        d, lang = details.get(row["id"], ("", None))
        row["dil"] = lang
        if d and d.isdigit():
            age = max((today - datetime.datetime.strptime(d, "%Y%m%d").date()).days, 1)
            row["yukleme"] = d
            row["gunluk_izlenme"] = round(row["izlenme"] / age)
            row["guncel"] = age <= 365

    table = ["| # | Başlık | Kanal | İzlenme | Günlük | Tarih |", "|---|---|---|---|---|---|"]
    for i, row in enumerate(rows, 1):
        row["baslik"] = (row["baslik"] or "").replace("|", "/")
        table.append(f"| {i} | {row['baslik']} | {row['kanal']} | {row['izlenme']:,} | "
                     f"{row.get('gunluk_izlenme', '?'):,} | {row.get('yukleme', '?')} |"
                     if isinstance(row.get('gunluk_izlenme'), int) else
                     f"| {i} | {row['baslik']} | {row['kanal']} | {row['izlenme']:,} | ? | ? |")
    result = {"sorgular": a.queries, "haric": a.exclude, "elenen": dropped,
              "filtre": {"shorts": a.shorts, "min_sure": a.min_duration, "max_sure": a.max_duration, "dil": a.lang},
              "videolar": rows, "tablo": "\n".join(table),
              "not": "Uyarlama = mekanizmayı al (merak, ters köşe, deneyim), başlığı/konuyu birebir alma."}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text)
    print(result["tablo"])
    print(f"elenen: süre {dropped['sure']} · müzik/reklam {dropped['gurultu']} · dil {dropped['dil']}", file=sys.stderr)


if __name__ == "__main__":
    main()
