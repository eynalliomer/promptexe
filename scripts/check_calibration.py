#!/usr/bin/env python3
"""Kalibrasyon kapısı: talimatla üretilen örnek açılışlar bütçeye uyuyor ve birbirinden gerçekten
farklı mı? Sayıları model değil bu script verir.

Neden: model kendi yazdığı metnin uzunluğunu sistematik olarak fazla tahmin eder (ölçülmüş örnek:
yazılan "60/62/58 kelime", gerçek 48/53/46). Kalibrasyon da bir ölçümdür; gözle yapılmaz.

Kullanım:
    python3 check_calibration.py kalibrasyon.md --budget analiz/butce.json [--section "Giriş"]
        [--sabit "God keep you, my lords and ladies."] [--tolerance 0.15] [--max-overlap 0.25]
    python3 check_calibration.py kalibrasyon.md --words 61 --chars 310

kalibrasyon.md biçimi: her örnek "## Örnek N — <konu>" başlığı ve altında ```text … ``` bloğu.
Blok yalnız seslendirilecek metni içerir (sahne notu yok). Script her örneği sayar, bütçeyle
kıyaslar, örnekler arası ortak 4-kelime dizisi oranını ölçer. --sabit ile verilen kimlik ifadeleri
(selam, gag) benzerlik hesabından çıkarılır — onların tekrarı bilinçlidir.

Çıkış kodu 0 = GEÇTİ, 1 = GEÇMEDİ. Çıktıdaki sayıları rapora olduğu gibi yaz.
"""
import argparse
import itertools
import json
import re
import sys

NGRAM = 4          # 4 kelimelik ortak dizi: kalıp tekrarını yakalar, tek tük ortak kelimeyi değil
MIN_SAMPLES = 3


def tr_lower(s):
    """Türkçe güvenli küçük harf: Python 'İ'.lower() → 'i̇' (noktalı birleşik karakter) verir ve
    'biçim' gibi aramaları kaçırır (2026-11-12)."""
    return s.replace("İ", "i").lower()


def samples(path):
    text = open(path, encoding="utf-8").read()
    parts = re.split(r"^##\s+", text, flags=re.M)[1:]
    out = []
    for p in parts:
        title = p.splitlines()[0].strip()
        m = re.search(r"```(?:text)?\n(.*?)```", p, flags=re.S)
        if m:
            out.append((title, m.group(1).strip()))
    return out


def words(s):
    return re.findall(r"[\w'’-]+", tr_lower(s))


def grams(ws):
    return {" ".join(ws[i:i + NGRAM]) for i in range(len(ws) - NGRAM + 1)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("path")
    p.add_argument("--budget", help="section_budget.py --json çıktısı")
    p.add_argument("--section", help="bütçedeki bölüm adının başı (varsayılan: ilk bölüm)")
    p.add_argument("--words", type=int)
    p.add_argument("--chars", type=int)
    p.add_argument("--sabit", action="append", default=[], help="benzerlikten çıkarılacak kimlik ifadesi")
    p.add_argument("--tolerance", type=float, default=0.15)
    p.add_argument("--max-overlap", type=float, default=0.25)
    a = p.parse_args()

    tw, tc, label = a.words, a.chars, "elle verilen hedef"
    if a.budget:
        try:
            b = json.load(open(a.budget, encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            sys.exit(f"HATA: bütçe dosyası okunamadı ({e}) — önce section_budget.py --json > butce.json")
        secs = b.get("bolumler") or []
        if a.section and a.section.lower() in ("toplam", "total", "tamami", "tümü"):
            # Shorts gibi kısa formatlarda kalibrasyon tüm metin üzerinden yapılır
            secs = [{"bolum": "Toplam", "baslangic": secs[0]["baslangic"], "bitis": secs[-1]["bitis"],
                     "kelime": b.get("toplam_kelime"), "karakter": b.get("toplam_karakter")}] if secs else []
        sec = next((s for s in secs if not a.section or s["bolum"].lower().startswith(a.section.lower())), None)
        if not sec:
            sys.exit(f"HATA: bütçede '{a.section}' bölümü yok. Var olanlar: {[s['bolum'] for s in secs]}")
        tw, tc, label = sec["kelime"], sec["karakter"], f"bütçe: {sec['bolum']} ({sec['baslangic']}–{sec['bitis']})"
    if not tw:
        sys.exit("HATA: hedef yok — --budget ya da --words ver.")

    smp = samples(a.path)
    errs = []
    if len(smp) < MIN_SAMPLES:
        errs.append(f"{len(smp)} örnek bulundu, en az {MIN_SAMPLES} gerekli ('## Örnek N' + ```text bloğu)")

    print(f"Hedef ({label}): ~{tw} kelime" + (f" · ~{tc} karakter" if tc else "") + f" · tolerans ±%{int(a.tolerance*100)}")
    print("| Örnek | Kelime | Sapma | Karakter | Sapma |\n|---|---|---|---|---|")
    for title, s in smp:
        w, c = len(s.split()), len(s)
        dw = (w - tw) / tw
        dc = (c - tc) / tc if tc else 0
        print(f"| {title[:40]} | {w} | {dw:+.0%} | {c} | " + (f"{dc:+.0%} |" if tc else "– |"))
        if abs(dw) > a.tolerance:
            errs.append(f"'{title[:30]}': {w} kelime, hedef ~{tw} ({dw:+.0%})")
        if tc and abs(dc) > a.tolerance:
            errs.append(f"'{title[:30]}': {c} karakter, hedef ~{tc} ({dc:+.0%})")

    fixed = set()
    for f in a.sabit:
        fixed |= grams(words(f))
    gs = [(t, grams(words(s)) - fixed) for t, s in smp]
    print("\nÖrnekler arası ortak 4-kelime dizisi (sabit ifadeler hariç):")
    for (t1, g1), (t2, g2) in itertools.combinations(gs, 2):
        ov = len(g1 & g2) / max(min(len(g1), len(g2)), 1)
        print(f"  {t1[:22]} ↔ {t2[:22]}: %{ov*100:.0f}")
        if ov > a.max_overlap:
            errs.append(f"'{t1[:20]}' ile '{t2[:20]}' çok benzer (%{ov*100:.0f} ortak dizi) — kural muğlak, kuralı düzelt")

    if errs:
        print("\nGEÇMEDİ:")
        for e in errs:
            print(" -", e)
        print("Uzunluk sapmasında örneği düzelt; benzerlikte talimattaki çeşitlilik kuralını düzelt.")
        sys.exit(1)
    print("\nSONUÇ: GEÇTİ")


if __name__ == "__main__":
    main()
