#!/usr/bin/env python3
"""MCP yolu (claude.ai / Cowork / yerel araç çalışmayan her ortam): analitik aracından (ör. Nexlev)
toplanan veriyi, yerel hattın ürettiğiyle AYNI şemada analiz.json'a çevirir. Ağ gerektirmez.

Kullanım:
    python3 build_from_mcp.py mcp_veri.json [--outdir analiz] [--hook 40]

Neden ayrı bir adım: MCP araç sonuçları sandbox'taki script'lere ulaşmaz; Claude yalnız gereken
alanları kısa bir mcp_veri.json'a (şema: references/mcp-yolu.md) ve transkriptleri metin
dosyalarına yazar. Hesaplar (medyan, outlier, yaş, tempo, giriş metni) burada deterministik yapılır —
modelin kafadan sayı tahmin etmesine yer bırakmaz.
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUTLIER_RATIO = 3.0   # fetch_channel.py ile aynı eşik
TOO_NEW_DAYS = 14     # henüz birikmemiş videoyu "zayıf" sayma

AGE_UNITS = {"second": 1 / 86400, "minute": 1 / 1440, "hour": 1 / 24, "day": 1, "week": 7, "month": 30,
             "year": 365, "saniye": 1 / 86400, "dakika": 1 / 1440, "saat": 1 / 24, "gün": 1, "hafta": 7,
             "ay": 30, "yıl": 365}


def age_days(text):
    """'8 years ago', '3 weeks ago', '2 gün önce' → gün (yaklaşık). Bilinmezse None."""
    if not text:
        return None
    m = re.search(r"(\d+)\s*([a-zA-ZğüşıöçĞÜŞİÖÇ]+)", str(text))
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower().rstrip("s")
    for k, v in AGE_UNITS.items():
        if unit.startswith(k):
            return n * v
    return None


def to_seconds(v):
    """'6:05', '1:00:01', 499, '499' → saniye."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    parts = [float(p) for p in str(v).split(":") if p.strip() != ""]
    s = 0.0
    for p in parts:
        s = s * 60 + p
    return s or None


def views(v):
    if isinstance(v, int):
        return v
    try:
        return int(str(v).replace(",", "").replace(".", ""))
    except (TypeError, ValueError):
        return None


def summarize(rows):
    viewed = [r for r in rows if isinstance(r.get("views"), int)]
    if not viewed:
        return {"count": len(rows), "with_views": 0}
    med = statistics.median(r["views"] for r in viewed)
    for r in viewed:
        r["outlier_score"] = round(r["views"] / med, 2) if med else None
        r["too_new"] = (r.get("age_days") or 9999) < TOO_NEW_DAYS
    ranked = sorted(viewed, key=lambda r: -r["views"])
    durs = [r["duration_s"] for r in rows if r.get("duration_s")]
    return {"count": len(rows), "with_views": len(viewed), "median_views": med,
            "outliers": [r["id"] for r in ranked if (r.get("outlier_score") or 0) >= OUTLIER_RATIO],
            "top": [r["id"] for r in ranked[:4]],
            "weakest": [r["id"] for r in ranked if not r["too_new"]][-3:],
            "median_duration_s": statistics.median(durs) if durs else None}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mcp_json")
    p.add_argument("--outdir", default="analiz")
    p.add_argument("--hook", type=int, default=40)
    a = p.parse_args()
    try:
        d = json.load(open(a.mcp_json, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"HATA: {a.mcp_json} okunamadı: {e}")
    os.makedirs(a.outdir, exist_ok=True)
    base = os.path.dirname(os.path.abspath(a.mcp_json))
    eksikler = []

    # Kanal listeleri: "yeni" (güncel format + outlier için doğru örneklem), "populer" (tüm zamanlar)
    tabs = {}
    for key in ("yeni", "populer", "shorts"):
        rows = []
        for v in (d.get("kanal_videolari") or {}).get(key) or []:
            rows.append({"id": v.get("id"), "title": v.get("baslik"), "views": views(v.get("izlenme")),
                         "duration_s": to_seconds(v.get("sure")), "age_days": age_days(v.get("yas_metni"))})
        if rows:
            tabs[key] = {"summary": summarize(rows), "videos": rows}
    if "yeni" not in tabs:
        eksikler.append("kanal_videolari.yeni yok — 'popular' sıralaması eski videolara kayar; outlier/zayıf seçimi güvenilmez")
    main_tab = tabs.get("yeni") or tabs.get("populer") or {"summary": {}}

    videos, transkriptler = [], []
    for v in d.get("videolar") or []:
        langs = v.get("altyazi_dilleri") or []
        auto = [x.get("kod") for x in langs if x.get("otomatik")]
        ses = (v.get("ses_dili") or (auto[0] if auto else None) or "").split("-")[0] or None
        tr_file = v.get("transkript_dosyasi")
        st = {}
        if tr_file:
            path = tr_file if os.path.isabs(tr_file) else os.path.join(base, tr_file)
            if os.path.exists(path):
                args = [sys.executable, os.path.join(HERE, "transcript_stats.py"), path, "--hook", str(a.hook), "--json"]
                if v.get("sure_sn"):
                    args += ["--duration", str(to_seconds(v["sure_sn"]))]
                if ses:
                    args += ["--lang", ses]
                r = subprocess.run(args, capture_output=True, text=True)
                st = json.loads(r.stdout) if r.returncode == 0 else {}
            else:
                eksikler.append(f"{v.get('id')}: transkript dosyası yok ({tr_file})")
        else:
            eksikler.append(f"{v.get('id')}: transkript yazılmamış")
        tdil = v.get("transkript_dili") or ses
        if st:
            transkriptler.append({"video_id": v.get("id"), "rol": v.get("rol"), "ses_dili": ses, "dil": tdil,
                                  "kaynak": "auto" if (tdil in auto or not auto) else "manual",
                                  "kelime_dk": st.get("words_per_min"), "capraz_kontrol": v.get("capraz_kontrol"),
                                  "dosya": tr_file})
        izl, beg = views(v.get("izlenme")), views(v.get("begeni"))
        videos.append({"video_id": v.get("id"), "rol": v.get("rol"),
                       "meta": {"baslik": v.get("baslik_orijinal"), "baslik_uzunluk": len(v.get("baslik_orijinal") or ""),
                                "sure_sn": to_seconds(v.get("sure_sn")), "izlenme": izl, "begeni": beg,
                                "begeni_orani": round(beg / izl, 4) if izl and beg else None,
                                "yorum_sayisi": views(v.get("yorum_sayisi")), "yukleme": v.get("yukleme"),
                                "etiketler": v.get("etiketler"),
                                "bolumler": [{"t": to_seconds(t), "baslik": b} for t, b in (v.get("aciklama_bolumleri") or [])],
                                "isi_haritasi": None, "yorumlar": v.get("yorumlar")},
                       "olcumler": {k: x for k, x in st.items() if k != "hook_text"},
                       "giris_metni": st.get("hook_text")})

    iz = d.get("izleme") or {}
    izleme = {"video_id": iz.get("video_id"), "pencere_sn": iz.get("pencere") or [0, a.hook],
              "kaynak": iz.get("kaynak") or "izlenmedi", "kesim_dk": iz.get("kesim_dk"),
              "gozlem": iz.get("gozlem"), "transkriptle_uyum": iz.get("transkriptle_uyum"),
              "kare_kolajlari": iz.get("kolaj_urlleri")}
    if izleme["kaynak"] == "izlenmedi":
        eksikler.append("video izlenmedi (araç/plan yok) — görsel bulgular 'varsayım' olarak işaretlenmeli")

    wpms = [t["kelime_dk"] for t in transkriptler if isinstance(t.get("kelime_dk"), (int, float))]
    k = d.get("kanal") or {}
    s = main_tab["summary"]
    analiz = {
        "referans": {"platform": d.get("platform", "youtube"), "link": d.get("referans_link"), "kanal": k.get("ad"),
                     "sekme": "shorts" if d.get("format") == "9:16" else "videos"},
        "kullanici": {"nis": None, "icerik_dili": None, "instruction_dili": None, "kitle": None,
                      "format": d.get("format", "16:9"), "hedef_sure": None, "uretim_yontemi": None,
                      "yuzlu": None, "hedef": None, "hedef_ai": None},
        "veri_kaynagi": d.get("kaynak", "mcp"),
        "kanal_verisi": {"incelenen_video": s.get("count"), "toplam_video": k.get("video_sayisi"),
                         "medyan_izlenme": s.get("median_views"), "outlier_sayisi": len(s.get("outliers", [])),
                         "medyan_sure_sn": s.get("median_duration_s"), "abone": k.get("abone"),
                         "sekmeler": {name: t["summary"] for name, t in tabs.items()},
                         "not": "MCP listelerinde tarih 'x yıl önce'den türetilir (yaklaşık); başlıklar çevrilmiş olabilir"},
        "transkriptler": transkriptler,
        "videolar": videos,
        "izleme": izleme,
        "kategori": None, "kanal_tipi": None,
        "tempo": {"kelime_dk": round(statistics.median(wpms), 1) if wpms else None, "hedef_kelime": None},
        "bulgular": [], "uyarlama": None,
        "sinirlar": eksikler[:],
        "rakip_adlari": sorted({x for x in [k.get("ad"), k.get("handle")] + (d.get("diger_adlar") or []) if x}),
    }
    out = os.path.join(a.outdir, "analiz.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(analiz, f, ensure_ascii=False, indent=2)
    print(json.dumps({"analiz_json": out,
                      "kanal": {n: {kk: t["summary"].get(kk) for kk in ("count", "median_views", "outliers", "weakest")}
                                for n, t in tabs.items()},
                      "videolar": [(v["video_id"], v["rol"], v["olcumler"].get("words_per_min")) for v in videos],
                      "izleme": izleme["kaynak"], "eksikler": eksikler}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
