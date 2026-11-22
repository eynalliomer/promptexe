#!/usr/bin/env python3
"""Bölüm bütçesi: hedef videonun her bölümü için SÜRE + KELİME + KARAKTER — referansın gerçek
konuşma hızından, bölüm bölüm ölçülerek.

Neden: instruction'ı kullanan model "0:00–0:30 giriş" gibi süreleri metin uzunluğuna çeviremez.
Her zaman dilimli bölüm kelime ve karakter karşılığıyla yazılmalı. Konuşma hızı bölüme göre değişir
(giriş genelde hızlı, kapanış yavaş) — tek bir ortalama kelime/dk ile çarpmak bu farkı siler.

Kullanım:
    python3 section_budget.py --target 11m tr/a.en.txt tr/b.en.txt [tr/c.en.txt] \
        --section "Giriş=0:30s" --section "Jenerik=30s:40s" --section "Gövde=40s:92%" \
        --section "Kapanış=92%:100%" [--lang-factor 1.0] [--json]

Bölüm sınırları saniye (30s), dakika:saniye (1:30) ya da hedef sürenin yüzdesi (92%) olabilir.
Saniye/dakika sınırları referansta da MUTLAK pencereden ölçülür (giriş her uzunlukta aynı
sürededir); yüzde sınırları referansın aynı ORAN penceresinden ölçülür.

--lang-factor: içerik dili referanstan farklıysa kelime sayısına çarpan (ör. EN→TR ≈ 0.8, çünkü
Türkçe sondan eklemeli; emin değilsen 1.0 bırak ve "ilk videodan sonra kalibre et" notu düş).
Karakterler her zaman referansın ölçümüdür.

Girdi: "[d:ss] metin" satırlı transkriptler (fetch_transcript.py ya da MCP yolundan). Her satırın
kelimeleri satırın başlangıç zamanına atanır (bölüm sınırlarında ±1 satır hassasiyet).
"""
import argparse
import json
import re
import sys

TS = re.compile(r"^\[(\d+):(\d+)(?::(\d+))?\]\s*(.*)$")


def load(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        m = TS.match(line.strip())
        if not m:
            continue
        a, b, c, txt = m.groups()
        t = int(a) * 3600 + int(b) * 60 + int(c) if c else int(a) * 60 + int(b)
        txt = re.sub(r"\[(music|müzik|música|musique|applause|risas)\]", "", txt, flags=re.I).strip()
        if txt:
            rows.append((t, txt))
    if not rows:
        sys.exit(f"HATA: {path} zaman damgalı satır içermiyor ([d:ss] metin).")
    return rows


def parse_point(s, total):
    s = s.strip().lower()
    if s.endswith("%"):
        return ("rel", float(s[:-1]) / 100.0)
    if s.endswith("s"):
        return ("abs", float(s[:-1]))
    if ":" in s:
        m, sec = s.split(":")
        return ("abs", int(m) * 60 + float(sec))
    return ("abs", float(s))


def dur_arg(s):
    s = s.strip().lower()
    if s.endswith("m"):
        return float(s[:-1]) * 60
    if ":" in s:
        m, sec = s.split(":")
        return int(m) * 60 + float(sec)
    return float(s.rstrip("s"))


def to_sec(point, total):
    kind, v = point
    return v * total if kind == "rel" else v


def mmss(s):
    return f"{int(s // 60)}:{int(round(s % 60)):02d}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("transcripts", nargs="+")
    p.add_argument("--target", required=True, help="hedef süre: 11m, 660, 11:00")
    p.add_argument("--section", action="append", required=True, help='"Ad=başlangıç:bitiş"')
    p.add_argument("--lang-factor", type=float, default=1.0)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    target = dur_arg(a.target)
    refs = []
    for path in a.transcripts:
        rows = load(path)
        refs.append((rows, rows[-1][0] + 3))  # son satır + ortalama satır süresi

    out = []
    for spec in a.section:
        if "=" not in spec or spec.split("=", 1)[1].count(":") < 1:
            sys.exit(f"HATA: bölüm biçimi 'Ad=başlangıç:bitiş' olmalı: {spec}")
        name, rng = spec.split("=", 1)
        # "1:30:2:00" gibi dakika:saniye sınırlarını desteklemek için son ':' öncesi/sonrası değil,
        # birimli sınırları ayır: önce %/s sonlu iki parçaya bölmeyi dene
        m = re.match(r"^\s*([\d.:]+[%s]?)\s*:\s*([\d.:]+[%s]?)\s*$", rng) or re.match(r"^\s*([^:]+):(.+)$", rng)
        lo, hi = parse_point(m.group(1), target), parse_point(m.group(2), target)
        t0, t1 = to_sec(lo, target), to_sec(hi, target)
        if t1 <= t0:
            sys.exit(f"HATA: {name}: bitiş başlangıçtan büyük olmalı")
        wps, cps = [], []
        for rows, rdur in refs:
            r0 = lo[1] * rdur if lo[0] == "rel" else lo[1]
            r1 = hi[1] * rdur if hi[0] == "rel" else hi[1]
            r1 = min(r1, rdur)
            if r1 - r0 < 3:
                continue
            txt = " ".join(x for t, x in rows if r0 <= t < r1)
            wps.append(len(txt.split()) / (r1 - r0))
            cps.append(len(txt) / (r1 - r0))
        if not wps:
            sys.exit(f"HATA: {name}: referanslarda bu pencere yok (referans videolar daha kısa olabilir)")
        w = sum(wps) / len(wps) * (t1 - t0) * a.lang_factor
        c = sum(cps) / len(cps) * (t1 - t0)
        out.append({"bolum": name.strip(), "baslangic": mmss(t0), "bitis": mmss(t1), "sure_sn": round(t1 - t0),
                    "kelime": int(round(w, -1 if w >= 100 else 0)), "karakter": int(round(c, -1)),
                    "kelime_dk_referans": round(sum(wps) / len(wps) * 60, 1)})

    total_w = sum(r["kelime"] for r in out)
    total_c = sum(r["karakter"] for r in out)
    lines = ["| Bölüm | Zaman | Süre | Kelime | Karakter (boşluk dahil) |", "|---|---|---|---|---|"]
    for r in out:
        lines.append(f"| {r['bolum']} | {r['baslangic']}–{r['bitis']} | {r['sure_sn']} sn | "
                     f"~{r['kelime']:,} | ~{r['karakter']:,} |")
    lines.append(f"| **Toplam** | 0:00–{mmss(target)} | {round(target)} sn | ~{total_w:,} | ~{total_c:,} |")
    note = (f"Referans: {len(refs)} transkript, bölüm bazında ölçülmüş konuşma hızı."
            + (f" Kelime sayısına dil çarpanı {a.lang_factor} uygulandı." if a.lang_factor != 1.0 else ""))
    if a.json:
        print(json.dumps({"bolumler": out, "toplam_kelime": total_w, "toplam_karakter": total_c,
                          "tablo": "\n".join(lines), "not": note}, ensure_ascii=False, indent=2))
    else:
        print("\n".join(lines))
        print("\n" + note)


if __name__ == "__main__":
    main()
