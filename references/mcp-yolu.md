---
title: MCP yolu — claude.ai / Cowork / yerel araç çalışmayan ortamlar
---

# MCP yolu

**Ne zaman:** `doctor.py` `erisimsiz` ya da `kurulamadi` dediğinde, ya da script çalıştırılamayan bir
ortamdaysan (claude.ai'de YouTube sunucu IP'lerini çoğu zaman engeller). Analiz yine eksiksiz yapılır;
yalnız veri bir analitik MCP aracından (aşağıda Nexlev örneği) gelir. Kullanıcıya iş düşmez.

## İçindekiler
1. Çağrı sırası (Nexlev)
2. Tuzaklar — bunları bilmeden analiz yanlış çıkar
3. İzleme: plan ve maliyete göre
4. `mcp_veri.json` şeması ve `build_from_mcp.py`
5. Piyasa konu havuzu (MCP)

## 1. Çağrı sırası (Nexlev)

Araç adları ortamda `<sunucu>:<araç>` ya da `mcp__…__<araç>` biçiminde görünür; listeden bul.
Ucuz metin araçlarını önce, birbirinden bağımsız olanları paralel çağır.

| # | Araç | Ne için | Not |
|---|---|---|---|
| 1 | `channel_resolver` | Link → kanal ID (UC…) | Video linki verildiyse önce `youtube_video_details` → `channelId` |
| 2 | `youtube_channel_videos` `sort_by: newest` | Güncel format, outlier ve zayıf video seçimi | **Asıl örneklem bu** |
| 3 | `youtube_channel_videos` `sort_by: popular` | Tüm zamanların kazananları | Eski videolara kayar; tek başına kullanma |
| 4 | `youtube_channel_shorts` | Shorts analizi gerekiyorsa | Uzun video ile ayrı özetlenir |
| 5 | `youtube_video_details` (seçilen her video) | **Orijinal** başlık, açıklama, bölümler (açıklamadaki zaman damgaları), etiket, süre, beğeni | Liste başlıkları çevrilmiş olabilir — başlık analizini buradan yap |
| 6 | `get_video_subtitle` | Altyazı dilleri; `(auto-generated)` olan **ses dilidir** | Elle yazılmış altyazı varsa (otomatik değil) daha güvenilirdir |
| 7 | `get_video_transcript` / `get_bulk_video_transcripts` (≤10) | Transkript (zaman damgalı) | Ses dilinde otomatik altyazı döner → isim/sayı çapraz kontrolü şart |
| 8 | `youtube_video_comments` `sort_by: top` | En beğenilen yorumlar | Kanal sahibinin sabit tanıtım yorumunu ayıkla |
| 9 | `check_faceless_channel` | Yüzlü/yüzsüz + format etiketi | İsteğe bağlı, hızlı |

Seçim: `newest` listesinden (14 günden genç olanlar hariç) en çok izlenen 3 + en az izlenen 1.
Kullanıcının verdiği video varsa o da girer.

## 2. Tuzaklar

- **Çevrilmiş başlıklar:** kanal listesi başlıkları arayüz diline (çoğu zaman İngilizce) çevrilmiş
  gelebilir. Başlık kalıbını, uzunluğunu ve dilini yalnız `youtube_video_details` başlığından çıkar.
- **Yaklaşık tarihler:** listelerdeki tarih "8 years ago" metninden türetilir. Yaş hesabını
  `yas_metni` üzerinden yap, gün hassasiyeti bekleme. Kesin tarih `youtube_video_details`'tadır.
- **Örtüşen transkript parçaları:** zaman pencereleri üst üste biner ama metin tekrar etmez —
  satırları sırayla birleştir.
- **Otomatik altyazı hataları:** sayılar ve özel adlar sık yanlış duyulur (gerçek örnek:
  ekranda "355 → 473 ml", altyazıda "35 a 473 ml"). Kanıt olarak kullanacağın her sayıyı
  açıklama, ekran (izleme varsa) ya da bağlamla doğrula; düzeltmeyi `capraz_kontrol`'e yaz.
- **Isı haritası yok:** Nexlev "en çok tekrar izlenen" verisini vermez. Bölümler + yorumlardaki
  zaman damgaları ("7:29 ufff") en yakın ikame — yorumlarda geçen dakikaları not et.

## 3. İzleme: plan ve maliyete göre

Sırayla dene; erişim hatası ("not available on your current plan") alırsan bir sonrakine geç,
kullanıcıyı plan ayrıntısıyla meşgul etme.

1. **`extract_video_frames_for_editing_animation_and_camera_style`** (ücretli planlar): ilk 40 sn için
   ~16 zaman damgası (0.5, 3, 5.5 … 38) tek çağrıda, `framesPerCollage: 16`. Asenkron:
   `get_video_frames_status` ile 5 sn arayla bekle. Kolaj URL'lerini görsel olarak aç; her karenin
   sol alt köşesinde zamanı yazar. Orta bölüm temposu için ikinci bir çağrıda 60 sn'lik pencereye
   1 sn arayla 16 kare.
2. **`watch_youtube_video_and_ask`** (pahalı — kullanıcıdan bir kez onay): `startOffset: "0s"`,
   `endOffset: "40s"` ve şu istem:
   > "Bu 40 saniyeyi sahne sahne listele: her plan için başlangıç saniyesi, görsel tür (çizim/AI
   > görseli/gerçek çekim/stok/ekran kaydı), kamera hareketi, ekrandaki yazı (birebir), yüz var mı.
   > Sonra: toplam kesim sayısı, renk paleti, altyazı/ekran yazısı stili, müzik ve ses efekti
   > kullanımı. Yorum katma, yalnız gözlem."
   Cevaptaki kesim sayısından `kesim_dk` = kesim ÷ (40/60).
3. **Hiçbiri yoksa:** `izleme.kaynak: "izlenmedi"`. Analiz durmaz; görsel bulgular "varsayım"
   olur (başlık kartı/kapak/açıklamadan çıkarılan ipuçları), `sinirlar`'a yazılır. Kullanıcıdan
   yalnız teslimde, tek cümleyle, isteğe bağlı olarak ekran görüntüsü önerilebilir.

## 4. `mcp_veri.json` ve `build_from_mcp.py`

MCP sonuçları sandbox'taki script'lere ulaşmaz. Ham JSON'u kopyalama (uzun ve hataya açık);
yalnız aşağıdaki alanları yaz, transkriptleri `tr/<id>.<dil>.txt` dosyalarına `[d:ss] metin`
satırlarıyla dök. Sonra:

```bash
python3 scripts/build_from_mcp.py mcp_veri.json --outdir analiz
```

Script medyanı, outlier'ları, yaşa göre zayıf videoyu, tempoyu ve giriş metnini hesaplar;
yerel hattınkiyle aynı şemada `analiz/analiz.json` üretir. Sonraki adımlar (yorum alanları,
`check_analysis.py`, instruction) iki yolda da aynıdır.

```json
{
  "kaynak": "nexlev", "platform": "youtube", "format": "16:9",
  "referans_link": "https://www.youtube.com/watch?v=…",
  "kanal": {"ad": "…", "handle": "@…", "id": "UC…", "abone": 4660000, "video_sayisi": null},
  "kanal_videolari": {
    "yeni":    [{"id": "…", "izlenme": 91558, "sure": "8:19", "yas_metni": "1 day ago"}],
    "populer": [{"id": "…", "izlenme": 8900000, "sure": "6:05", "yas_metni": "8 years ago"}],
    "shorts":  []
  },
  "videolar": [
    {"id": "…", "rol": "verilen|populer|zayif",
     "baslik_orijinal": "…", "sure_sn": 499, "izlenme": 91558, "begeni": 3182, "yorum_sayisi": 153,
     "yukleme": "2026-11-08", "etiketler": ["…"],
     "aciklama_bolumleri": [["0:00", "Intro"], ["0:22", "Ingredientes"]],
     "altyazi_dilleri": [{"kod": "es", "otomatik": true}, {"kod": "es-419", "otomatik": false}],
     "transkript_dosyasi": "tr/<id>.es.txt", "transkript_dili": "es",
     "capraz_kontrol": "ASR '35 a 473 ml' → '355 → 473 ml'",
     "yorumlar": [{"begeni": 150, "metin": "…"}]}
  ],
  "izleme": {"kaynak": "nexlev_kare | nexlev_izle | izlenmedi", "video_id": "…", "pencere": [0, 40],
             "kesim_dk": 4.5, "gozlem": "…", "transkriptle_uyum": "…", "kolaj_urlleri": ["…"]},
  "diger_adlar": ["sunucu adı", "seri adı"]
}
```

Bulunmayan alanı `null` bırak; uydurma. `diger_adlar`, teslim kontrolünde rakip adı sızıntısını
yakalamak için kullanılır (sunucu, maskot, seri adları).

## 5. Piyasa konu havuzu (MCP)

Kullanıcının nişi belli olunca (formdan sonra), instruction'ın "B) piyasadan uyarlama" konu
seçenekleri için. Sorguları analizden türet (referansın konu tipi + kullanıcının nişi), 2–3 çağrı:

| Araç | Parametreler | Ne verir |
|---|---|---|
| `search_videos` | `query`: niş kelimeleri · `minOutlierScore: "2"` · `startDate`: bugün − 12 ay · `minLength` (uzun format için "3:00") · `sortBy: "outlierScore"` · `limit: 30` | Kanal ortalamasını ezmiş, son bir yılın videoları |
| `faceless_outliers_videos` | `query`: içeriğin doğal dil tarifi (ör. "AI-narrated medieval daily life vlog") · `videoType: "long"` · `minOutlierScore: 2` | Yüzsüz/AI format outlier'ları — anlamsal arama |
| `search_viral_videos_small_channels` | `query` · `maxChannelSubCount: 50000` · `sortBy: "videoViews"` | Son 90 gün, küçük kanal kırılmaları (format henüz doymamış mı?) |

Plan erişimi yoksa ya da sonuç boşsa: yerel `market_topics.py` (Yol A). İkisi de yoksa B seçeneği
atlanır ve bu söylenir — veri uydurulmaz. Formata uymayan gürültüyü (oyun, tepki videosu, derleme)
ele. Tabloya: kaynak başlık · kanal · izlenme · outlier skoru (varsa) · tarih · bizdeki karşılık.
