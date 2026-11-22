#!/usr/bin/env python3
"""Tek komutla tüm ölçülebilir analiz: kanal → video seçimi → orijinal dil transkript → tempo →
metadata (bölümler, ısı haritası, yorumlar) → giriş izleme + orta bölüm kurgu temposu.

Kullanım:
    python3 analyze_reference.py <kanal_veya_video_linki> [--outdir analiz/] [--tab auto|videos|shorts]
                                 [--top 3] [--hook 40] [--thumbs]

Kullanıcıya iş bırakmaz: her adım kendi yedeğine düşer, düşemezse "eksikler"e yazar ve devam eder.
Çıktılar <outdir>/ altında; özet stdout'a. analiz.json ölçülebilir alanlarla DOLU gelir —
Claude yalnız yorum alanlarını (gozlem, kategori, kanal_tipi, bulgular, uyarlama) doldurur.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import _env  # noqa: E402
_env.ensure_venv_python()

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
MIDDLE_SAMPLE_S = 60   # orta bölümden kurgu temposu örneği; 60 sn tek sahnenin tesadüfünü dengeler
TOP_COMMENTS = 20


def script(name, *args, timeout=1800):
    r = subprocess.run([PY, os.path.join(HERE, name), *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr.strip().splitlines()[-1:] if r.stderr.strip() else []


def ytdlp_json(url, comments=False, save=None):
    cmd = _env.ytdlp_base() + ["--no-warnings", "--skip-download", "--no-playlist", "-J"]
    if comments:
        cmd += ["--write-comments", "--extractor-args",
                f"youtube:max_comments={TOP_COMMENTS},all,0;comment_sort=top"]
    r = subprocess.run(cmd + ["--", url], capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    if save:
        with open(save, "w", encoding="utf-8") as f:
            f.write(r.stdout)
    return json.loads(r.stdout)


def heat_peaks(heatmap, duration):
    """En çok tekrar izlenen 3 an (ilk %5 hariç: giriş her videoda yüksek görünür)."""
    if not heatmap:
        return None
    pts = [h for h in heatmap if h.get("start_time", 0) > (duration or 0) * 0.05]
    top = sorted(pts, key=lambda h: -h.get("value", 0))[:3]
    early = [h["value"] for h in heatmap if h.get("start_time", 0) < 30]
    later = [h["value"] for h in heatmap if 30 <= h.get("start_time", 0) < 90]
    return {
        "zirveler_sn": [int(h["start_time"]) for h in top],
        "ilk30_ort": round(statistics.mean(early), 3) if early else None,
        "30_90_ort": round(statistics.mean(later), 3) if later else None,
        "not": "değer = göreli tekrar izlenme (0-1); retention değil, en yakın açık gösterge",
    }


def video_meta(url, comments, save=None):
    d = ytdlp_json(url, comments=comments, save=save)
    if not d:
        return None
    m = {
        "id": d.get("id"), "baslik": d.get("title"), "baslik_uzunluk": len(d.get("title") or ""),
        "aciklama": (d.get("description") or "")[:1500], "etiketler": d.get("tags"),
        "sure_sn": d.get("duration"), "izlenme": d.get("view_count"), "begeni": d.get("like_count"),
        "yorum_sayisi": d.get("comment_count"), "abone": d.get("channel_follower_count"),
        "dil": d.get("language"), "yukleme": d.get("upload_date"),
        "bolumler": [{"t": int(c["start_time"]), "baslik": c.get("title")} for c in d.get("chapters") or []],
        "isi_haritasi": heat_peaks(d.get("heatmap"), d.get("duration")),
        "kapak_url": d.get("thumbnail"),
        "kanal": d.get("channel"), "kanal_url": d.get("channel_url"), "yukleyen": d.get("uploader"),
    }
    if m["izlenme"] and m["begeni"]:
        m["begeni_orani"] = round(m["begeni"] / m["izlenme"], 4)
    if comments:
        m["yorumlar"] = [{"begeni": c.get("like_count"), "metin": (c.get("text") or "")[:300]}
                         for c in (d.get("comments") or [])[:TOP_COMMENTS]]
    return m


def main():
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--outdir", default="analiz")
    p.add_argument("--tab", default="auto", choices=["auto", "videos", "shorts"])
    p.add_argument("--top", type=int, default=3)
    p.add_argument("--hook", type=int, default=40)
    p.add_argument("--thumbs", action="store_true", help="kapakları da indir (kullanıcı istediyse)")
    a = p.parse_args()
    out = os.path.abspath(a.outdir)
    os.makedirs(out, exist_ok=True)
    eksikler, log = [], []

    # 1) Link video mu kanal mı?
    is_video = any(k in a.url for k in ("watch?v=", "youtu.be/", "/shorts/", "/video/", "/reel/", "/p/"))
    given = video_meta(a.url, comments=False) if is_video else None
    channel_url = (given or {}).get("kanal_url") if is_video else a.url
    tab = a.tab
    if tab == "auto":
        tab = "shorts" if "/shorts/" in a.url else "videos"

    # 2) Kanal verisi
    kanal = None
    if channel_url:
        rc, so, se = script("fetch_channel.py", channel_url, "--limit", "30", "--tab", tab,
                            "--out", os.path.join(out, "kanal.json"))
        if rc == 0:
            kanal = json.load(open(os.path.join(out, "kanal.json"), encoding="utf-8"))
            log.append("kanal: " + so.strip().replace("\n", " | "))
        else:
            eksikler.append(f"kanal verisi çekilemedi: {se}")
    tabdata = (kanal or {}).get("tabs", {}).get(tab) or (kanal or {}).get("tabs", {}).get("videos") or {}
    vids = [v for v in tabdata.get("videos", []) if isinstance(v.get("views"), int)]

    # 3) Video seçimi: verilen video + en iyi N + en zayıf 1 — fetch_channel'ın format ve yaş
    #    düzeltmeli sıralamasından (olgun kanalda toplam izlenme, genç kanalda günlük izlenme)
    summ = tabdata.get("summary", {})
    picks = []
    if given:
        picks.append((given["id"], "verilen"))
    for vid in summ.get("top", []):
        if len([x for x in picks if x[1] in ("verilen", "populer")]) >= a.top:
            break
        if vid not in [x[0] for x in picks]:
            picks.append((vid, "populer"))
    ref_lang = None  # popülerlerin ses dili: zayıf seçimi ve dilsiz videoların ASR ipucu için
    chosen = [x[0] for x in picks]
    weak = [w for w in (summ.get("weak_candidates") or summ.get("weakest", [])[::-1]) if w not in chosen]
    if weak and len(vids) >= 4:
        # Zayıf aday, popülerlerle aynı SES DİLİNDE olmalı (çok dilli kanalda başka dilde bir yan seri
        # "en zayıf" çıkabiliyor). Dil tek hafif çağrıyla, paralel çekilir; bilinmiyorsa kabul edilir.
        base0 = "https://www.youtube.com/shorts/" if tab == "shorts" else "https://www.youtube.com/watch?v="

        def lang_of(vid):
            r = subprocess.run(_env.ytdlp_base() + ["--no-warnings", "--skip-download", "--no-playlist",
                                                     "--print", "%(language)s", base0 + vid],
                               capture_output=True, text=True, timeout=180)
            v = (r.stdout.strip().splitlines() or [""])[-1].strip()
            return vid, (None if v in ("", "NA", "None") else v.split("-")[0].lower())

        ref_ids = chosen[:2]
        with ThreadPoolExecutor(max_workers=6) as ex:
            langs = dict(ex.map(lang_of, ref_ids + weak[:4]))
        ref_lang = next((langs[i] for i in ref_ids if langs.get(i)), None)
        pick_w = next((w for w in weak[:4] if not ref_lang or not langs.get(w) or langs[w] == ref_lang), None)
        skipped = [w for w in weak[:4] if pick_w and weak.index(w) < weak.index(pick_w)]
        if skipped:
            log.append(f"zayıf aday ses dili farklı, atlandı: {', '.join(f'{w}({langs[w]})' for w in skipped)}")
        if pick_w:
            picks.append((pick_w, "zayif"))
        else:
            eksikler.append(f"zayıf video seçilemedi: ilk 4 aday farklı dilde ({ref_lang} değil)")
    if not picks:
        eksikler.append("incelenecek video seçilemedi")
    base = "https://www.youtube.com/shorts/" if tab == "shorts" else "https://www.youtube.com/watch?v="

    def per_video(item):
        vid, rol = item
        url = base + vid if len(vid) == 11 else vid
        res = {"video_id": vid, "rol": rol, "url": url}
        os.makedirs(os.path.join(out, "tr"), exist_ok=True)
        info_path = os.path.join(out, "tr", f"{vid}.info.json")
        meta = video_meta(url, comments=(rol in ("verilen",) or (rol == "populer" and not given and item == picks[0])),
                          save=info_path)
        res["meta"] = meta
        extra = ["--info-json", info_path] if os.path.exists(info_path) else []
        hint = ["--lang-hint", ref_lang] if ref_lang else []
        rc, so, se = script("fetch_transcript.py", url, "--also", "en", "--outdir", os.path.join(out, "tr"), "--asr",
                            *extra, *hint)
        if rc == 0 and json.loads(so).get("konusma_yok"):
            tm = json.loads(so)
            res.update({"ses_dili": tm["audio_lang"], "konusma_yok": True, "kaynak": "asr",
                        "not": "anlatım yok (yalnız müzik/efekt) — tempo ölçülmedi; popülerlerle format farkı"})
        elif rc == 0:
            tm = json.loads(so)
            lang = tm["audio_lang"]
            path = tm["files"][lang]["path"]
            rc2, so2, _ = script("transcript_stats.py", path, "--lang", lang, "--hook", str(a.hook), "--json",
                                 *(["--duration", str(meta["sure_sn"])] if meta and meta.get("sure_sn") else []))
            st = json.loads(so2) if rc2 == 0 else {}
            res.update({"ses_dili": lang, "dil": lang, "kaynak": tm["files"][lang]["source"],
                        "dosya": path, "capraz_dosya": (tm["files"].get("en") or {}).get("path"),
                        "kelime_dk": st.get("words_per_min"), "olcumler": st,
                        "capraz_kontrol": None if tm["files"][lang]["source"] != "manual" else "elle yazılmış altyazı"})
        else:
            res["hata"] = f"transkript: {se}"
        return res

    # İzleme, transkriptleri beklemez: ana videonun girişi ve orta bölümü transkriptlerle AYNI ANDA çekilir.
    # (Sıralı akışta izleme en sona kalıyordu; toplam sürenin ~%25'i.)
    main_pick = next((p_ for p_ in picks if p_[1] == "verilen"), None) or next((p_ for p_ in picks if p_[1] == "populer"), None)
    main_url = (base + main_pick[0] if len(main_pick[0]) == 11 else main_pick[0]) if main_pick else None
    main_dur = (given or {}).get("sure_sn") if main_pick and main_pick[1] == "verilen" else \
        next((v.get("duration_s") for v in vids if main_pick and v["id"] == main_pick[0]), None)

    def watch(args):
        return script("watch_video.py", main_url, *args)

    with ThreadPoolExecutor(max_workers=6) as ex:
        f_hook = ex.submit(watch, ["--end", str(a.hook), "--outdir", os.path.join(out, "izleme")]) if main_url else None
        f_mid = None
        if main_url and main_dur and main_dur > a.hook + MIDDLE_SAMPLE_S * 2:
            mid = int(main_dur / 2)
            f_mid = ex.submit(watch, ["--start", str(mid), "--end", str(mid + MIDDLE_SAMPLE_S), "--cuts-only",
                                      "--outdir", os.path.join(out, "izleme-orta")])
        videos = list(ex.map(per_video, picks))
        hook_res = f_hook.result() if f_hook else None
        mid_res = f_mid.result() if f_mid else None
    for v in videos:
        if v.get("hata"):
            eksikler.append(f"{v['video_id']}: {v['hata']}")

    # Kanal listesi başlık ÇEVİRİSİ verebilir (çok dilli başlık kullanan kanallar): video bazlı meta
    # orijinali verir. Fark varsa başlık kalıbı analizi liste başlıklarıyla yapılmamalı.
    list_titles = {x["id"]: x.get("title") for x in vids}
    cevrilmis = [{"id": v["video_id"], "liste": list_titles[v["video_id"]], "orijinal": v["meta"]["baslik"]}
                 for v in videos if (v.get("meta") or {}).get("baslik") and list_titles.get(v["video_id"])
                 and list_titles[v["video_id"]].strip().casefold() != v["meta"]["baslik"].strip().casefold()]
    if cevrilmis:
        eksikler.append(f"kanal listesi ÇEVRİLMİŞ başlık veriyor ({len(cevrilmis)}/{len(videos)} incelenen videoda "
                        "farklı) — başlık kalıbı ve dil analizi yalnız videolar[].meta.baslik ile yapılır; "
                        "kanal.json başlıkları orijinal sayılmaz")

    # 4) İzleme: ana video (verilen ya da en popüler) — giriş kareleri + orta bölüm kesim temposu
    izleme = None
    main_v = next((v for v in videos if main_pick and v["video_id"] == main_pick[0]), None)
    if main_v and hook_res:
        rc, so, se = hook_res
        if rc == 0:
            w = json.loads(so)
            izleme = {"video_id": main_v["video_id"], "pencere_sn": w["window"], "kaynak": "watch_video",
                      "kesim_dk_giris": w["cuts_per_min"], "kesimler": w["cuts"], "kareler": len(w.get("frames", [])),
                      "gorsel_degisim_dk_giris": w.get("visual_changes_per_min"),
                      "yumusak_gecis": bool(w.get("soft_transitions")),
                      "temas_sayfasi": w.get("contact_sheet"), "kare_dosyalari": [f["path"] for f in w.get("frames", [])],
                      "gozlem": None, "transkriptle_uyum": None}
            if mid_res and mid_res[0] == 0:
                mw = json.loads(mid_res[1])
                izleme["kesim_dk_orta"] = mw["cuts_per_min"]
                izleme["gorsel_degisim_dk_orta"] = mw.get("visual_changes_per_min")
                izleme["yumusak_gecis"] = izleme["yumusak_gecis"] or bool(mw.get("soft_transitions"))
            izleme["kesim_dk"] = izleme.get("kesim_dk_orta", izleme["kesim_dk_giris"])
            if izleme["yumusak_gecis"]:
                # Sert kesim sayımı bu kurguda tempoyu küçük gösterir; sahne bütçesi görsel değişimden gelir
                izleme["kesim_dk"] = izleme.get("gorsel_degisim_dk_orta") or izleme["gorsel_degisim_dk_giris"]
        else:
            eksikler.append(f"izleme yapılamadı: {se} → analitik aracının izleme aracını kullan")

    if a.thumbs:
        import urllib.request
        os.makedirs(os.path.join(out, "kapaklar"), exist_ok=True)
        for v in videos:
            u = (v.get("meta") or {}).get("kapak_url")
            if u:
                try:
                    urllib.request.urlretrieve(u, os.path.join(out, "kapaklar", v["video_id"] + ".jpg"))
                except Exception:
                    eksikler.append(f"kapak indirilemedi: {v['video_id']}")

    # 5) analiz.json iskeleti — ölçülenler dolu, yorumlar boş
    wpms = [v["kelime_dk"] for v in videos if isinstance(v.get("kelime_dk"), (int, float))]
    names = {x for x in [(kanal or {}).get("channel")] + [(v.get("meta") or {}).get("kanal") for v in videos]
             + [(v.get("meta") or {}).get("yukleyen") for v in videos] if x}
    s = tabdata.get("summary", {})
    analiz = {
        "referans": {"platform": "youtube" if "youtu" in a.url else "diger", "link": a.url,
                     "kanal": (kanal or {}).get("channel"), "sekme": tab},
        "kullanici": {"nis": None, "icerik_dili": None, "instruction_dili": None, "kitle": None,
                      "format": "9:16" if tab == "shorts" else "16:9", "hedef_sure": None,
                      "uretim_yontemi": None, "yuzlu": None, "hedef": None, "hedef_ai": None},
        "veri_kaynagi": "yt-dlp",
        "kanal_verisi": {"incelenen_video": s.get("count"), "toplam_video": None,
                         "medyan_izlenme": s.get("median_views"), "outlier_sayisi": len(s.get("outliers", [])),
                         "medyan_sure_sn": s.get("median_duration_s"), "tarih_araligi": s.get("date_range"),
                         "yan_seriler": s.get("seriler", []), "liste_basligi_cevrilmis": cevrilmis,
                         "sekmeler": {k: v.get("summary") for k, v in (kanal or {}).get("tabs", {}).items()}},
        "transkriptler": [{k: v.get(k) for k in ("video_id", "rol", "ses_dili", "dil", "kaynak", "kelime_dk",
                                                 "capraz_kontrol", "dosya", "capraz_dosya")} for v in videos if v.get("dosya")],
        "videolar": [{"video_id": v["video_id"], "rol": v["rol"], "meta": v.get("meta"),
                      **({"konusma_yok": True} if v.get("konusma_yok") else {}),
                      "olcumler": {k: x for k, x in (v.get("olcumler") or {}).items() if k != "hook_text"},
                      "giris_metni": (v.get("olcumler") or {}).get("hook_text")} for v in videos],
        "izleme": izleme or {"gozlem": None, "transkriptle_uyum": None},
        "kategori": None, "kanal_tipi": None,
        "tempo": {"kelime_dk": round(statistics.median(wpms), 1) if wpms else None, "hedef_kelime": None},
        "bulgular": [], "uyarlama": None,
        "sinirlar": eksikler[:] + ([f"kanal küçük: {s.get('count')} video"] if (s.get("count") or 0) < 5 else []),
        "rakip_adlari": sorted(names),
    }
    with open(os.path.join(out, "analiz.json"), "w", encoding="utf-8") as f:
        json.dump(analiz, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "analiz_json": os.path.join(out, "analiz.json"),
        "videolar": [(v["video_id"], v["rol"], v.get("ses_dili"), v.get("kelime_dk")) for v in videos],
        "izleme": {k: (izleme or {}).get(k) for k in ("kesim_dk_giris", "kesim_dk_orta", "gorsel_degisim_dk_giris", "gorsel_degisim_dk_orta", "yumusak_gecis", "kareler", "temas_sayfasi")},
        "eksikler": eksikler,
        "simdi_sen": [
            "temas sayfasını ve gerekirse kare dosyalarını Read ile aç → izleme.gozlem + transkriptle_uyum",
            "transkriptleri (dosya) oku; otomatik altyazıysa capraz_dosya ile isim/sayı kontrolü → capraz_kontrol",
            "kategori, kanal_tipi, ≥6 bulgu (veri/varsayım + kanıt), uyarlama",
            "kullanici alanlarını tek formdaki cevaplarla doldur; tempo.hedef_kelime = hedef süre × kelime_dk",
            "check_analysis.py ile doğrula",
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
