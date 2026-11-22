---
title: Analiz rehberi — ne çıkarılır, nasıl kaydedilir
---

# Analiz rehberi

**Ne zaman oku:** Akışın 2. adımında (otomatik analiz bitince) ve 4. adımda (yorum alanlarını doldururken). Analiz hem instruction'ın hammaddesi hem de kendi başına
bir teslim (kullanıcı "sadece analiz et" diyebilir).

## İçindekiler
1. Çıkarılacaklar (detaylı rakip analizi)
2. `analiz.json` şeması
3. Kullanıcıya sunulan analiz raporu

## 1. Çıkarılacaklar

Her madde için **sayı, alıntı ya da zaman damgası** ile kanıt ara. Bulamazsan "varsayım" de.

**Kanal ve dağıtım**
- Kanal tipi ve içerik kategorisi (arama / öneri / trend / hype) — gerekçe görüntülenme
  dağılımından: aramada eski videolar izlenmeye devam eder; öneride dağılım dalgalı, outlier belirgin.
- Yükleme sıklığı, video süreleri (medyan), uzun/Shorts oranı, yüzlü/yüzsüz.
- Outlier'lar ve ortak noktaları (konu, başlık kalıbı, süre). 14 günden genç videoları "zayıf" sayma.
- Kazanan / kaybeden farkı: en iyi 2–4 ile en zayıf 1–2 video arasında başlık, konu, giriş farkı.

**Paket**
- Başlık kalıbı (boşluk, çelişki, maliyet-kazanç, adlandırılmış ilke…), ortalama uzunluk.
- Açıklama formülü (boşsa "boş" de). Kapak yalnız istenirse ya da SS verildiyse.

**Giriş (ilk 30–40 sn)**
- İlk cümle ne yapıyor (sahne, iddia, soru, tanıma)? İlk bilgi kaçıncı saniyede?
- Açık döngü sayısı ve zamanları; vaat başlıkla uyumlu mu?
- Marka tanıtımı / "abone ol" var mı, ne zaman?

**Script**
- Anlatı iskeleti ve bölüm payları (% süre); merak köprüleri; bitiş tipi.
- Tempo: kelime/dk (orijinal dil), ortalama/en uzun cümle, soru oranı, hitap (2. tekil oranı).
- Anlatım kalitesi: ayrıntı düzeyi, duygunun verilişi (söyleme mi, davranışla mı), tekrarlar.
- **Kimlik kalıpları** (kanalı kanal yapan, sabit tutulacak) vs **tembellik kalıpları**
  (her videoda aynı cümle/yapı — "seri üretim riski", taşınmayacak).

**Görsel akış ve ses**
- Görsel tür (AI görsel/klip, gerçek çekim, stok, animasyon); stok medya hangi bölümde.
- Kesim sıklığı (sn/kesim), kamera hareketi, palet, altyazı/ekran yazısı stili, müzik ve ses.
- Ardışık görselli format ise tahmini sahne sayısı = süre ÷ kesim sıklığı.

**İzleyici sinyalleri (hattın topladığı ücretsiz veriler)**
- **Isı haritası** (`isi_haritasi`): en çok tekrar izlenen anlar. Retention değildir ama en yakın
  açık göstergedir: zirvelerin denk geldiği transkript satırları videonun "para sahneleri"dir —
  hangi tür an (açıklama, ters köşe, liste maddesi, duygu) tekrar izletiyor? `ilk30_ort` vs
  `30_90_ort` farkı girişten sonraki düşüşün kabaca göstergesi.
- **Bölümler** (`bolumler`): script iskeletinin kanalın kendi elinden yazılmış hali; bölüm
  sürelerini oranlara çevir.
- **Yorumlar** (`yorumlar`, en beğenilenler): kitlenin neye tepki verdiği, hangi dili kullandığı,
  ne istediği. Kanal sahibinin sabitlenmiş tanıtım yorumunu ayıkla.
- **Beğeni oranı** (`begeni_orani`): kanal içinde videoları kıyaslamak için; kanallar arası kıyaslama yapma.

**Sınırlar**
- Örnek küçüklüğü (yeni kanal, az video), izlenemeyen kısımlar, otomatik altyazı hataları.

## 2. `analiz.json` şeması

Analizi bu dosyaya yaz ve `python3 scripts/check_analysis.py analiz.json` ile denetle.
**GEÇTİ** demeden instruction'a (5. adım) geçme — kapı, yorgun anda atlanan adımları yakalamak için var.

`analyze_reference.py` bu dosyayı ölçülebilir alanlar dolu olarak üretir (ek olarak `videolar[]`:
meta, ölçümler, giriş metni). Senin doldurduğun: `izleme.gozlem`, `izleme.transkriptle_uyum`,
`transkriptler[].capraz_kontrol` (otomatik altyazıda), `kategori`, `kanal_tipi`, `bulgular`,
`uyarlama`, `kullanici`, `tempo.hedef_kelime`. Kullanıcı yalnız analiz istediyse `"mod": "sadece_analiz"`.

```json
{
  "mod": "tam | sadece_analiz",
  "referans": {"platform": "youtube|instagram|tiktok", "link": "...", "kanal": "..."},
  "kullanici": {"nis": "...", "icerik_dili": "tr", "instruction_dili": "tr", "kitle": "35+ TR",
                 "format": "16:9", "hedef_sure": "12-15 dk", "uretim_yontemi": "Higgsfield",
                 "yuzlu": false, "hedef": "...", "hedef_ai": "claude | gpt | gem | system"},
  "veri_kaynagi": "nexlev | yt-dlp | kullanici",
  "kanal_verisi": {"incelenen_video": 30, "toplam_video": 140, "medyan_izlenme": 120000,
                    "outlier_sayisi": 3, "medyan_sure_sn": 780, "yukleme_sikligi": "haftada 2"},
  "transkriptler": [
    {"video_id": "...", "rol": "populer|zayif", "ses_dili": "es", "dil": "es",
     "kaynak": "manual|auto|asr", "kelime_dk": 148.2, "capraz_kontrol": "en parçası ile 3 isim düzeltildi"}
  ],
  "izleme": {"video_id": "...", "pencere_sn": [0, 40], "kaynak": "watch_video | nexlev | kullanici_ss",
             "kesim_dk": 4.5, "kareler": 12,
             "gozlem": "2D çizim, turuncu fon; 13.8 sn başlık kartı; 18-21 sn kanal jeneriği; 28 sn gerçek ürün fotoğrafı; ekran yazısı İspanyolca, rakam vurgulu",
             "transkriptle_uyum": "uyumlu | şu noktada uyuşmuyor: ..."},
  "kategori": "oneri",
  "kanal_tipi": "hikaye",
  "tempo": {"kelime_dk": 148, "hedef_kelime": "1780-2220"},
  "bulgular": [
    {"alan": "giris|script|tempo|gorsel|paket|dil|dagitim", "bulgu": "...",
     "dayanak": "veri|varsayim", "kanit": "00:07'de ilk açık döngü; 3/3 videoda aynı"}
  ],
  "uyarlama": "formatın kullanıcının konusuna nasıl taşınacağı",
  "sinirlar": ["kanal 4 aylık, 22 video"],
  "rakip_adlari": ["Kanal Adı", "Sunucu Adı", "seri adı"]
}
```

`hedef_kelime` = kullanıcının hedef süresi (dk) × referansın kelime/dk'sı. Kullanıcının içerik
dili referansınkinden farklıysa bunu söyle: diller arası kelime/dk farklıdır, hedefi ilk
videodan sonra kullanıcının kendi seslendirmesiyle kalibre etmesini öner.

`rakip_adlari` teslim kontrolünde kullanılır: instruction'da bu adların hiçbiri geçmemeli.

## 3. Kullanıcıya sunulan analiz raporu (TEYİT 2)

Kısa, taranabilir; her satır veri mi varsayım mı belli olsun:

```
KANAL TİPİ / KATEGORİ: … (gerekçe: …)
VERİ: N video, medyan …, outlier … · transkript: … (dil, kaynak) · izleme: …
GİRİŞ: …                      [veri: 00:05, 00:18, 00:31'de 3 açık döngü]
SCRIPT İSKELETİ: …            [veri]
TEMPO: … kelime/dk → hedef … kelime   [veri]
GÖRSEL: …                     [veri/varsayım]
PAKET: başlık kalıbı …        [veri: 4/4 outlier'da]
KİMLİK (koru): … · TEMBELLİK (taşıma): …
UYARLAMA ÖNERİSİ: …
SINIRLAR: …
Sahne promptu gerekecek mi? Kaç sahne? (tahmin: …)
```

Kullanıcı yalnız analiz istediyse burada dur ve raporu teslim et (artifact ya da .md).
