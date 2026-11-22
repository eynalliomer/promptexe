#!/usr/bin/env python3
"""Teslim öncesi kapı: yazılan instruction sızıntı, kopya ve eksik bölüm içeriyor mu?

Kullanım:
    python3 check_instruction.py instruction.md analiz.json [transkript.txt ...] [--target claude|gpt|gem|system]

Denetler:
  1. Sızıntı — analiz.json'daki rakip_adlari instruction'da geçiyor mu (büyük/küçük harf duyarsız).
  2. Kopya — instruction ile verilen transkriptler arasında 8 kelimelik ortak dizi var mı.
     (Yapı kopyalanır, cümle kopyalanmaz.)
  3. Zorunlu içerik — tekrara düşmeme/çeşitlilik, başlık kuralı, iş akışı (adım adım teslim),
     uyum/dürüstlük, tempo/uzunluk hedefi (sayı ile).
  4. Uzunluk — hedef platformun sınırı (Custom GPT talimat alanı 8.000 karakter) ve makul aralık.
  5. Bütçe — süreli bölümlerin kelime + karakter karşılığı (ilke 10).
  6. Piyasa konuları — kaynak + izlenme + bizdeki karşılığı (ilke 11; veri yoksa piyasa_durumu: "yok").
  7. Numune — sahne promptu bölümü varsa zamanlı numune (ilke 12).
Çıkış kodu 0 = geçti, 1 = sorun var.
"""
import json
import re
import sys

# Hedef başına karakter sınırı: (sert sınır, açıklama). Bilinmeyen sınırı uydurmuyoruz.
TARGET_LIMITS = {
    "gpt": (8000, "Custom GPT talimat alanı 8.000 karakter; fazlasını 'Knowledge' dosyasına böl"),
    "gem": (None, "Gemini Gem için belgelenmiş sınır bilinmiyor; 8.000 karakteri aşıyorsa ayrıntıyı ek dosyaya böl"),
    "claude": (None, None),
    "system": (None, None),
}
NGRAM = 8  # 8 kelimelik ortak dizi tesadüf olamayacak kadar uzun, kalıp ifadeyi yakalamayacak kadar kısa

# Bölüm/ilke varlığını dil bağımsız aramak için TR + EN anahtar kelimeler
REQUIRED = {
    "çeşitlilik / tekrara düşmeme": r"çeşitlilik|tekrar|dönüşüm|variety|vary|rotat|repetit",
    "başlık kuralı": r"başlık|title",
    "iş akışı (adım adım teslim)": r"iş akışı|adım|workflow|step",
    "uyum / dürüstlük": r"uyum|uydurma|yanıltıcı|ifşa|policy|disclos|mislead|fabricat",
    "tempo / uzunluk": r"kelime|words?\b|wpm|dakika|minute",
}


def tr_lower(s):
    """Türkçe güvenli küçük harf: Python 'İ'.lower() → 'i̇' (noktalı birleşik karakter) verir ve
    'biçim' gibi aramaları kaçırır (2026-11-12)."""
    return s.replace("İ", "i").lower()


def words(text):
    return re.findall(r"\w+", tr_lower(text))


def main():
    argv = sys.argv[1:]
    target = "claude"
    if "--target" in argv:
        i = argv.index("--target")
        target = argv[i + 1] if i + 1 < len(argv) else "claude"
        argv = argv[:i] + argv[i + 2:]
    if target not in TARGET_LIMITS:
        sys.exit(f"HATA: --target {target} bilinmiyor (claude|gpt|gem|system)")
    sys.argv = [sys.argv[0]] + argv
    if len(sys.argv) < 3:
        sys.exit("Kullanım: check_instruction.py instruction.md analiz.json [transkript.txt ...] [--target ...]")
    try:
        ins = open(sys.argv[1], encoding="utf-8").read()
        an = json.load(open(sys.argv[2], encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"HATA: dosya okunamadı: {e}")
    errs, warns = [], []

    low = tr_lower(ins)
    for name in an.get("rakip_adlari") or []:
        # Tam kelime/ifade eşleşmesi: "Kate" adı "KATEGORİ" içinde yakalanmamalı
        if name and re.search(r"(?<!\w)" + re.escape(name.lower()) + r"(?!\w)", low):
            errs.append(f"SIZINTI: rakip adı geçiyor → '{name}'")

    iw = words(ins)
    igrams = {" ".join(iw[i:i + NGRAM]) for i in range(len(iw) - NGRAM + 1)}
    for path in sys.argv[3:]:
        raw = re.sub(r"^\[\d+:\d+\]\s*", "", open(path, encoding="utf-8").read(), flags=re.M)
        tw = words(raw)
        hits = {" ".join(tw[i:i + NGRAM]) for i in range(len(tw) - NGRAM + 1)} & igrams
        if hits:
            ex = next(iter(hits))
            errs.append(f"KOPYA: {path} ile {len(hits)} ortak {NGRAM}-kelime dizisi (ör. \"{ex}\")")

    for label, pat in REQUIRED.items():
        if not re.search(pat, low):
            errs.append(f"EKSİK: '{label}' ile ilgili kural bulunamadı")
    if not re.search(r"\d{2,4}\s*(-|–|ile)?\s*\d{0,4}\s*(kelime|words)", low):
        warns.append("Tempo/uzunluk hedefi sayı ile yazılmamış görünüyor (ör. '1.800–2.100 kelime')")

    # İlke 10 — süre → kelime + karakter bütçesi (tablo ya da en az 3 sayısal karakter karşılığı)
    budget_table = re.search(r"\|[^\n]*(kelime|words)[^\n]*\|[^\n]*(karakter|char)", low)
    char_nums = re.findall(r"~?\d[\d.,]*\s*(?:karakter|kr\b|chars?\b|characters)", low)
    if not budget_table and len(char_nums) < 3:
        errs.append("BÜTÇE: süreli bölümlerin kelime + karakter karşılığı yok (section_budget.py tablosunu ekle)")

    # İlke 11 — piyasadan uyarlanmış konu seçenekleri (veri yoksa analiz.json'da piyasa_durumu: "yok")
    if an.get("piyasa_durumu") != "yok":
        has_pool = re.search(r"konu havuzu|topic pool", low)
        has_market = re.search(r"(izlenme|views)", low) and re.search(r"(bizdeki karşılı|our version|uyarla)", low)
        if not (has_pool and has_market):
            errs.append("KONU: piyasadan uyarlanmış konu seçenekleri (kaynak + izlenme + bizdeki karşılığı) yok "
                        "— market_topics.py / mcp-yolu.md §5; veri yoksa analiz.json'a piyasa_durumu: \"yok\"")

    # İlke 12 — sahne promptu bölümü varsa zamanlı numune şart
    if re.search(r"sahne prompt|scene prompt", low):
        beats = re.findall(r"\b\d{1,2}(?:[.,]\d)?\s*[–-]\s*\d{1,2}(?:[.,]\d)?\s*(?:sn|s|sec)\b", low)
        # Shorts'ta vuruşlar ayrı promptlar olarak [00:10,2–00:12,0] biçiminde de yazılabilir
        beats += re.findall(r"\d{1,2}:\d{2}(?:[.,]\d)?\s*[–-]\s*\d{1,2}:\d{2}(?:[.,]\d)?", low)
        if len(beats) < 3:
            errs.append("NUMUNE: sahne promptları var ama zamanlı numune yok (ör. 0–2 sn / 2–4 sn / 4–6 sn vuruşları)")
        elif not re.search(r"biçim örneği|format example|numune", low):
            warns.append("Numune sahne promptunda 'BİÇİM ÖRNEĞİ — içeriğini kopyalama' notu yok")

    limit, note = TARGET_LIMITS[target]
    if limit and len(ins) > limit:
        errs.append(f"UZUNLUK: {len(ins)} karakter > {target} sınırı {limit} — {note}")
    elif note and len(ins) > 8000:
        warns.append(f"{len(ins)} karakter — {note}")
    n = len(iw)
    if n < 400:
        warns.append(f"Instruction kısa ({n} kelime) — analizden çıkan kurallar yeterince aktarılmamış olabilir")
    elif n > 4500:
        warns.append(f"Instruction çok uzun ({n} kelime) — Project instruction'da kural yoğunluğu dikkati dağıtır")

    for w in warns:
        print("UYARI", w)
    for e in errs:
        print(e)
    if errs:
        print(f"\nSONUÇ: GEÇMEDİ — {len(errs)} sorun. Düzelt ve yeniden çalıştır.")
        sys.exit(1)
    print(f"SONUÇ: GEÇTİ — {n} kelime, {len(ins)} karakter (hedef: {target}).")


if __name__ == "__main__":
    main()
