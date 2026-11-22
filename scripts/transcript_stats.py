#!/usr/bin/env python3
"""Transkriptten tempo ve anlatım ölçüleri çıkarır — kural yazmadan önce sayılar.

Kullanım:
    python3 transcript_stats.py <transkript.txt> [--duration 754] [--hook 40] [--json]

Girdi: "[mm:ss] metin" satırları (fetch_transcript.py çıktısı) ya da düz metin.
Düz metinde süre --duration (saniye) ile verilmelidir; yoksa tempo hesaplanamaz.

Çıktı: toplam kelime/karakter, kelime/dk, karakter/dk, ortalama ve en uzun cümle (kelime),
soru cümlesi oranı, ikinci tekil hitap oranı (en/es/tr/pt kaba sezgisi), giriş penceresi
(ilk --hook saniye) metni ve o penceredeki soru sayısı.
"""
import argparse
import json
import re
import sys

TS = re.compile(r"^\[(\d+):(\d+)\]\s*(.*)$")
# Kaba ikinci tekil hitap işaretleri; dil başına birkaç sık kalıp. Kesin değil, eğilim gösterir.
YOU = {
    "en": r"\b(you|your|you're|yourself)\b",
    "es": r"\b(tú|tu|te|ti|usted|tienes|puedes|eres)\b",
    "pt": r"\b(você|voce|seu|sua|te|tu)\b",
    "tr": r"\b(sen|seni|sana|senin|siz|sizin)\b|\w+(sın|sin|sun|sün|ın|in|un|ün)\b",
}


def load(path):
    rows, plain = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = TS.match(line)
            if m:
                rows.append((int(m.group(1)) * 60 + int(m.group(2)), m.group(3)))
            else:
                plain.append(line)
    return rows, " ".join(plain)


def sentences(text):
    parts = re.split(r"(?<=[.!?¿¡…])\s+", text)
    return [s for s in (p.strip() for p in parts) if len(s.split()) >= 2]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("path")
    p.add_argument("--duration", type=float, help="saniye; zaman damgası yoksa zorunlu")
    p.add_argument("--hook", type=int, default=40, help="giriş penceresi, saniye")
    p.add_argument("--lang", default=None, help="hitap ölçümü için: en, es, pt, tr")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    rows, plain = load(a.path)
    text = " ".join(x for _, x in rows) if rows else plain
    if not text:
        sys.exit("HATA: transkript boş.")
    duration = a.duration
    if not duration and rows:
        # Son satırın başlangıcı + ortalama satır süresi kadar pay
        duration = rows[-1][0] + 3
    words = text.split()
    sents = sentences(text)
    lens = [len(s.split()) for s in sents] or [len(words)]
    r = {
        "words": len(words),
        "chars": len(text),
        "duration_s": duration,
        "words_per_min": round(len(words) / (duration / 60), 1) if duration else None,
        "chars_per_min": round(len(text) / (duration / 60), 1) if duration else None,
        "sentences": len(sents),
        "avg_sentence_words": round(sum(lens) / len(lens), 1),
        "max_sentence_words": max(lens),
        "question_ratio": round(sum(1 for s in sents if s.endswith("?")) / max(len(sents), 1), 3),
    }
    if a.lang in YOU:
        hits = len(re.findall(YOU[a.lang], text, flags=re.IGNORECASE))
        r["second_person_per_100w"] = round(hits * 100 / len(words), 2)
    if rows:
        hook = " ".join(x for t, x in rows if t < a.hook)
        r["hook_window_s"] = a.hook
        r["hook_text"] = hook
        r["hook_words"] = len(hook.split())
        r["hook_questions"] = hook.count("?")
    else:
        r["note"] = "Zaman damgası yok: giriş penceresi çıkarılamadı."
    if not duration:
        r["warning"] = "Süre bilinmiyor: --duration ver, yoksa tempo kuralı yazılamaz."

    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        for k, v in r.items():
            if k != "hook_text":
                print(f"{k}: {v}")
        if "hook_text" in r:
            print(f"--- ilk {a.hook} sn ---\n{r['hook_text']}")


if __name__ == "__main__":
    main()
