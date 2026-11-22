# Değişiklikler

## 5.5 — 2026-11-12

Üç farklı formatta (uzun yüzsüz belgesel, 3D animasyonlu Shorts, Türkçe kamera önü anlatım)
uçtan uca testten çıkan düzeltmeler.

- **Zayıf video seçimi:** kanalın ana formatı olmayan numaralı seriler (≥3 video, ör.
  "… 9. Gün Özeti") zayıf aday olamaz; aday ses dili popüler videolarla aynı olmalı.
- **Çevrilmiş başlık uyarısı:** kanal listesi çevrilmiş başlık veriyorsa uyarı düşülür; başlık
  kalıbı yalnız video bazlı orijinal başlıkla incelenir.
- **Piyasa taraması:** `--lang`, `--min-duration`, `--max-duration`, `--shorts`; müzik klibi ve
  marka reklamı elemesi (`--keep-noise` ile kapanır).
- **Konuşmasız video:** Whisper VAD ile çalışır; anlatımsız video `konusma_yok` işaretlenir ve
  bulgu sayılır. Dil bilgisi yoksa kanalın dili ipucu olarak kullanılır; ses indirmesi bir kez
  yeniden denenir.

## 5.4 — 2026-11-12

- Otomatik altyazı artık "elle yazılmış" etiketlenmiyor; bölgesel elle varyant (en-GB, tr-TR) doğrudan istenir.
- Yumuşak geçişli kurguda (crossfade, parallax) görsel değişim dHash ile ölçülür; sahne bütçesi buradan gelir.
- Whisper'a ses ffmpeg ile çözülmüş dizi olarak verilir (PyAV `metadata_errors` çökmesi); altyazı inmezse bir kez yeniden denenir.
- Türkçe büyük "İ" kapılarda doğru küçültülür.
- Kalibrasyon kapısında `--section Toplam`; numune vuruşları `00:10,2–00:12,0` biçimini de kabul eder.

## 5.3 ve öncesi

- 5.3: analiz hattı paralel (6 dk → 40 sn), piyasa taraması 211 → 14 sn.
- 5.2: kalibrasyon kapısı (`check_calibration.py`).
