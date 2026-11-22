#!/usr/bin/env python3
"""Analiz kapısı (akışın 4. adımı): analiz dosyası eksiksiz mi? Geçmeden instruction yazılmaz.

Kullanım:
    python3 check_analysis.py analiz.json

Analiz dosyasının şeması: references/analiz-semasi.md. Bu script, analizin "atlanmaya
meyilli" adımlarını (orijinal dil transkript, çapraz kontrol, izleme, tempo, veri/varsayım
ayrımı) makine ile denetler. Çıkış kodu 0 = geçti, 1 = eksik var (her eksik ayrı satırda).
"""
import json
import sys

MIN_TRANSCRIPTS = 2      # 1 transkript tek videonun tesadüfünü kural sanmaya yol açar
SMALL_CHANNEL = 5        # bundan az videolu kanalda tek transkript kabul (uyarıyla)


def main():
    if len(sys.argv) != 2:
        sys.exit("Kullanım: check_analysis.py analiz.json")
    try:
        a = json.load(open(sys.argv[1], encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"HATA: analiz dosyası okunamadı: {e}")

    errs, warns = [], []

    def need(path, cond, msg):
        if not cond:
            errs.append(f"[{path}] {msg}")

    only_analysis = a.get("mod") == "sadece_analiz"
    u = a.get("kullanici") or {}
    if not only_analysis:
        for k in ("nis", "icerik_dili", "instruction_dili", "format", "hedef_sure", "hedef_ai"):
            need(f"kullanici.{k}", u.get(k), "boş — çıkarılamıyorsa tek formda sorulmalıydı")

    kv = a.get("kanal_verisi") or {}
    need("kanal_verisi.incelenen_video", (kv.get("incelenen_video") or 0) > 0, "kanal verisi çekilmemiş")
    need("veri_kaynagi", a.get("veri_kaynagi"), "hangi araçla çekildiği yazılmamış (nexlev | yt-dlp | kullanici)")

    trs = a.get("transkriptler") or []
    total_videos = kv.get("toplam_video") or kv.get("incelenen_video") or 0
    min_tr = 1 if total_videos and total_videos < SMALL_CHANNEL else MIN_TRANSCRIPTS
    need("transkriptler", len(trs) >= min_tr, f"{len(trs)} transkript var, en az {min_tr} gerekli")
    silent_weak = any(v.get("rol") == "zayif" and v.get("konusma_yok") for v in a.get("videolar") or [])
    if trs and not silent_weak and not any(t.get("rol") == "zayif" for t in trs):
        warns.append("[transkriptler] zayıf video transkripti yok — kazanan/kaybeden farkı kanıtsız kalır")
    for i, t in enumerate(trs):
        p = f"transkriptler[{i}]"
        need(p + ".dil", t.get("dil") and t.get("dil") == t.get("ses_dili"),
             f"transkript dili ({t.get('dil')}) ses diliyle ({t.get('ses_dili')}) aynı değil — orijinal dil şart")
        need(p + ".kelime_dk", isinstance(t.get("kelime_dk"), (int, float)), "tempo ölçülmemiş (transcript_stats.py)")
        if t.get("kaynak") in ("auto", "asr"):
            need(p + ".capraz_kontrol", t.get("capraz_kontrol"),
                 "otomatik metin ama çapraz kontrol notu yok (özel ad/sayı hataları)")

    iz = a.get("izleme") or {}
    if iz.get("kaynak") == "izlenmedi":
        # Ortamda izleme yolu yoksa (araç/plan) analiz durmaz; ama bunun dürüstçe kayıtlı olması şart
        warns.append("[izleme] video izlenmedi — görsel bulgular 'varsayim' olmalı")
        need("sinirlar", any("izlen" in str(x) for x in (a.get("sinirlar") or [])),
             "izlenmediği sinirlar'a yazılmamış")
        for i, b in enumerate(a.get("bulgular") or []):
            if b.get("alan") == "gorsel" and b.get("dayanak") == "veri" and "kapak" not in str(b.get("kanit", "")).lower():
                errs.append(f"[bulgular[{i}]] video izlenmediği halde görsel bulgu 'veri' etiketli")
    else:
        need("izleme.gozlem", iz.get("gozlem"), "ilk 30-40 sn izlenmemiş")
        need("izleme.transkriptle_uyum", iz.get("transkriptle_uyum"), "izleme gözlemi transkriptle karşılaştırılmamış")
    if iz.get("gozlem") and not iz.get("kaynak"):
        warns.append("[izleme.kaynak] izlemenin nasıl yapıldığı yazılmamış (watch_video | nexlev | kullanici_ss)")
    if iz.get("kaynak") == "watch_video" and not isinstance(iz.get("kesim_dk"), (int, float)):
        errs.append("[izleme.kesim_dk] watch_video kullanıldı ama kesim temposu yazılmamış")

    need("kategori", a.get("kategori"), "kanal kategorisi (arama/öneri/trend/hype) belirlenmemiş")
    tempo = a.get("tempo") or {}
    if not only_analysis:
        need("tempo.hedef_kelime", tempo.get("hedef_kelime"), "hedef süreye göre kelime sayısı hesaplanmamış")

    bl = a.get("bulgular") or []
    need("bulgular", len(bl) >= 6, f"{len(bl)} bulgu — detaylı analiz için en az 6 (giriş, script, tempo, görsel, paket, dil)")
    alanlar = {b.get("alan") for b in bl}
    for zorunlu in ("giris", "script", "paket"):
        need(f"bulgular[{zorunlu}]", zorunlu in alanlar, "bu alanda bulgu yok")
    for i, b in enumerate(bl):
        need(f"bulgular[{i}].dayanak", b.get("dayanak") in ("veri", "varsayim"), "veri/varsayım etiketi yok")
        if b.get("dayanak") == "veri":
            need(f"bulgular[{i}].kanit", b.get("kanit"), "'veri' dendi ama kanıt (sayı/alıntı/zaman) yok")
    if bl and all(b.get("dayanak") == "varsayim" for b in bl):
        errs.append("[bulgular] hepsi varsayım — analiz veriye dayanmıyor")

    need("rakip_adlari", a.get("rakip_adlari"), "sızıntı kontrolü için rakip kanal/kişi adları listelenmemiş")

    for w in warns:
        print("UYARI", w)
    if errs:
        for e in errs:
            print("EKSİK", e)
        print(f"\nSONUÇ: GEÇMEDİ — {len(errs)} eksik. Eksikleri tamamla, script'i yeniden çalıştır.")
        sys.exit(1)
    print("SONUÇ: GEÇTİ — instruction yazımına geçilebilir.")


if __name__ == "__main__":
    main()
