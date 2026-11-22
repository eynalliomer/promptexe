---
title: Instruction yazımı — bölümler, zorunlu ilkeler, kalite çıtası
---

# Instruction yazımı

**Ne zaman oku:** Akışın 5. adımında (analiz kapısı GEÇTİ'den sonra).

## İçindekiler
1. Bölümler
2. Zorunlu ilkeler
3. Kalite çıtası (oynaklığa karşı)
4. Kalibrasyon ve teslim kapısı
5. Hedef platform

## 1. Bölümler

Bölümleri kanala göre belirle — gereksizi at, gerekeni ekle. Tipik iskelet:
ROL · KONU ALANI · KONU HAVUZU · KATEGORİ VE KİTLE · BAŞLIK FORMÜLÜ · GİRİŞ · SCRIPT İSKELETİ ·
UZUNLUK VE TEMPO · CÜMLE SEVİYESİ SES · ÇEŞİTLİLİK VE TEKRARA DÜŞMEME · GERÇEKÇİLİK VE UYUM ·
GÖRSEL KALİTE · SAHNE PROMPTLARI (yalnız ardışık görselli formatlarda) · KAPAK (yalnız istenirse) ·
İŞ AKIŞI · ÇIKTI KURALLARI.

Instruction **kendi başına çalışır**: onu okuyan Claude analizi, rakibi ve bu sohbeti görmez.
Her kural, gerekçesiyle birlikte o Claude'un anlayacağı şekilde yazılır.

## 2. Zorunlu ilkeler

1. **Konuya uygun dil.** Her yeni konuda sözlük, benzetme ve ayrıntılar o konuya göre seçilir.
   Kalite sabit kalır, kelimeler kopyalanmaz.
2. **Tekrara düşmeme.** Analizden çıkan 4–6 dönüşümlü açılış tipi, bölüm sayısı/yapı varyasyonu,
   bitiş çeşitleri, ana metafor; her metnin sonunda tek satırlık çeşitlilik raporu; kullanıcı
   geçmiş raporları yapıştırırsa aynı kombinasyonu seçme. Referansın videoları aynı kalıpla
   yazılmışsa "seri üretim riski" notu düş ve her videoda en az 2–3 öğeyi değiştirmeyi zorunlu kıl
   (özgün olmayan içerik para kazanmayı riske atar).
3. **Algoritma uyumu.** Giriş, açık döngü, merak köprüsü ve başlık-kapak-giriş uyumu kategoriye göre.
4. **Başlık ve açıklama.** Kazanan kalıptan türet; her konu için 5 aday, birini gerekçesiyle öner.
   ~70 karakteri geçmesin, vaat dürüst ve ölçülü, başlıktaki sonuç videoda teslim edilsin.
5. **Uyum kontrolleri** (bkz. `dagitim-mantigi.md` §7) — ilgili olanlar kısa kural olarak girer.
6. **Stok medya ve ardışık görsel** — analizde çıktıysa bölüm yaz.
7. **Sahne promptları** — kullanıcı sahne sayısını verdiyse: sabit stil bloğu her promptun başına,
   her sahne kendi başına eksiksiz, karakter tutarlılığı için referans görsel kuralı. Script önce
   teslim edilip onaylanır, sahne promptları ayrı adımda. En-boy oranı araç parametresidir,
   prompt metnine yazılmaz.
8. **İş akışı bölümü** tek adımda tek teslim ister: konu önerisi → tam script → başlık ve açıklama →
   (isteğe bağlı) kapak → sahne sayısı ve sahne promptları. Sonraki adıma onaysız geçilmez.
9. **Kanıtlanmış / varsayım** ayrımı instruction'a da taşınır: varsayıma dayanan kurallar
   "başlangıç noktası — kendi Studio verinle güncelle" diye işaretlenir.
10. **Süre her yerde kelime + karakter karşılığıyla.** Instruction'ı kullanan model "0:00–0:30"u
    metin uzunluğuna çeviremez. GİRİŞ, SCRIPT İSKELETİ ve süreyle tarif edilen her bölüm
    `section_budget.py` tablosuyla yazılır: zaman · süre · ~kelime · ~karakter. Bütçe referansın
    gerçek konuşma hızından, bölüm bölüm ölçülür (giriş genelde gövdeden hızlıdır — tek ortalama
    kullanma). Script çıktısının sonuna bölüm başına "bütçe / gerçekleşen kelime" sapma satırı istenir
    (±%15 dışı bölüm kısaltılır ya da genişletilir). Instruction bu sayımın **kod çalıştırarak**
    yapılmasını, yapılamıyorsa "(tahmini)" etiketini şart koşar — gözle sayım sistematik olarak fazladır.
11. **Konu havuzu iki kaynaklı.** A) Instruction'ın kendi ürettiği konular (analizdeki kazanan
    konu tiplerinden). B) Piyasada tutmuş videolardan uyarlama: kurulum sırasında
    `market_topics.py` (ya da MCP arama araçları, `mcp-yolu.md` §5) ile bulunan 8–12 videoyu
    tabloya koy — kaynak başlık · izlenme · günlük izlenme · **bizdeki karşılığı** (mekanizma
    alınır, başlık/konu birebir alınmaz). Ayrıca instruction'a kalıcı kural yaz: "Bu projede bir
    YouTube analitik aracı (ör. Nexlev: `search_videos` minOutlierScore≥2 son 12 ay,
    `faceless_outliers_videos` anlamsal arama) bağlıysa, her konu önerisi turunda önce piyasayı
    tara ve B seçeneklerini kaynak + sayılarla sun; araç yoksa B'yi atla, veri uydurma."
12. **Numune sahne promptu.** Ardışık görselli formatlarda instruction, alan listesinin yanında
    **bir adet** tam doldurulmuş, zamanlı numune içerir: ör. 8 sn'lik sahne → `0–2 sn / 2–4 sn /
    4–6 sn / 6–8 sn` vuruşları, her vuruşta görüntü + hareket + (varsa) replik/ses; üstte sabit
    stil bloğu, altta kamera ve SFX. Üstüne "BİÇİM ÖRNEĞİ — içeriğini kopyalama" notu düşülür.
    Biçim tariften değil numuneden öğrenilir.

## 3. Kalite çıtası — oynaklığa karşı

Aynı analizden iki kez yazılan instruction aynı kaliteyi vermeli. Bunun için her kural şu
dört testi geçer:

| Test | Zayıf | Güçlü |
|---|---|---|
| **Ölçülebilir mi?** | "Girişi güçlü yap." | "İlk 30 sn'de 2–3 açık döngü aç; ilki ilk 8 sn'de; hiçbirini 3. dakikadan önce kapatma." |
| **Gerekçeli mi?** | "Cümleler kısa olsun." | "Cümleler ortalama 9–12 kelime; dinleyici yaşlı ve videoyu arka planda dinliyor, uzun cümlede kopuyor." |
| **Konudan bağımsız mı?** | "Bir pastanenin hikâyesini anlat." | "Her hikâye: sıradan bir esnaf, somut bir borç rakamı, bir kırılma kararı." |
| **Kopyadan uzak mı?** | Rakibin açılış cümlesinin çevirisi | Açılış *tipinin* tarifi + 4–6 tipin dönüşümü |

Kendi kendine kontrol: instruction'daki her kuralın `analiz.json`'daki bir bulguya ya da
dağıtım çerçevesine dayandığını gösterebilmelisin. Dayanağı olmayan kuralı çıkar.

Kalite çıtası için bir örnek: `assets/ornek-instruction.md` — **şablon değil**; yapısını
kopyalama, yalnız ayrıntı ve gerekçe seviyesini ölçü al.

## 4. Kalibrasyon ve teslim kapısı

1. `python3 scripts/check_instruction.py instruction.md analiz.json tr/*.txt --target <hedef>` →
   GEÇTİ olana kadar düzelt (sızıntı, 8 kelimelik kopya, eksik ilke, bütçe tablosu, piyasa
   konuları, numune sahne promptu, platform uzunluk sınırı).
2. Kalibrasyon: instruction'ı kullanarak 3 farklı konuda giriş yaz ve `check_calibration.py` ile
   ölç (bütçe sapması ±%15, örnekler arası ortak 4-kelime dizisi ≤%25; sabit selam/gag hariç).
   Uzunluk tutmuyorsa örneği düzelt; örnekler benzeşiyorsa kural muğlaktır — kuralı düzelt, örneği
   değil. Sayıları script'ten al: model kendi metninin uzunluğunu fazla tahmin eder (ölçülmüş:
   "60/62/58" yazıldı, gerçek 48/53/46).
3. Teslim et. Revizyon isteğe bağlıdır; kullanıcı istemedikçe ayrıca sorma.

## 5. Hedef platform

Instruction'ın kullanılacağı yer formda seçilir; `check_instruction.py --target` ile denetlenir.

| Hedef | Kural |
|---|---|
| Claude Project (`claude`) | Tek instruction; uzun referans bilgisi gerekiyorsa Project bilgi dosyası olarak ayrı ver |
| Custom GPT (`gpt`) | Talimat alanı **8.000 karakter** (sert sınır). Çekirdek kurallar talimatta; örnekler, kanal tipi ayrıntısı, başlık havuzu "Knowledge" dosyasında. Talimata "ayrıntı için ekli dosyaya bak" yaz |
| Gemini Gem (`gem`) | Belgelenmiş sınırı bilmiyoruz; 8.000 karakteri aşıyorsa ayrıntıyı ek dosyaya böl |
| Ham system prompt (`system`) | API / otomasyon (n8n vb.) için; çıktı formatını makinece ayrıştırılabilir yaz (ör. bölüm etiketleri sabit) |

Hangi hedef olursa olsun içerik aynı kalite çıtasından geçer; yalnız paketleme değişir.
