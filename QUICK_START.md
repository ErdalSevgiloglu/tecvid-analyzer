# TECVID ANALYZER - HIZLI BAŞLANGIÇ (5 DAKİKA) ⚡

## 1️⃣ Python Backend Kurulumu (Terminal 1)

```bash
# Repo klonla veya dosyaları hazırla
cd tecvid_backend

# Virtual env oluştur
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# veya: venv\Scripts\activate  # Windows

# Bağımlılıkları yükle
pip install Flask Flask-CORS librosa numpy scipy soundfile

# Backend'i başlat
python tecvid_backend.py
# ✅ Output: Running on http://0.0.0.0:5000
```

## 2️⃣ Flutter Uygulaması Kurulumu (Terminal 2)

```bash
cd flutter_app

# Bağımlılıkları yükle
flutter pub get

# URL'yi ayarla
# 📝 flutter_main_screen.dart dosyasında:
# static const String BACKEND_URL = 'http://localhost:5000';
# (veya Android emulator için: 'http://10.0.2.2:5000')

# Uygulamayı çalıştır
flutter run

# Cihaz seç:
# - Chrome (browser test)
# - Android emulator
# - iOS simulator
# - Fiziksel cihaz
```

## 3️⃣ Test Et

1. **Uygulama açılsın**
2. **"Bismillah" söyle** (bissmillahirrahmanirrahim)
3. **"Analiz Et" butonuna bas**
4. ✅ **Sonuçlar görünsün:**
   ```
   Toplam Skor: 82%
   
   Detay:
   - Telaffuz: iyi
   - Med: iyi  
   - Harf: geliştirilmeli
   ```

---

## 📋 Dosya Yapısı

```
tecvid_analyzer/
├── backend/
│   ├── tecvid_backend.py       ← Flask server
│   ├── requirements.txt         ← Python paketleri
│   └── test_audio.wav          ← Test ses dosyası
│
├── flutter_app/
│   ├── lib/
│   │   ├── main.dart
│   │   ├── flutter_main_screen.dart   ← Ekranlar
│   │   └── tecvid_analyzer.dart       ← Dart analiz sınıfları
│   ├── pubspec.yaml             ← Flutter paketleri
│   └── assets/
│       └── audios/
│           ├── bismillah_reference.wav
│           ├── alhamdulillah_reference.wav
│           └── ...
│
└── docs/
    └── SETUP_GUIDE.md           ← Detaylı kurulum rehberi
```

---

## 🔧 Yaygın Sorunlar & Çözümler

### ❌ "Connection refused" (Flask çalışmıyor)
```bash
✅ Önce terminal 1'de: python tecvid_backend.py
✅ Port 5000'in açık olduğundan emin ol
✅ Firewall izni ver (macOS/Windows)
```

### ❌ "No such file or directory: tecvid_backend.py"
```bash
✅ Dosyaların doğru klasörde olduğundan emin ol
✅ Dosya türünü kontrol et (.py, .dart, .wav)
```

### ❌ "Microphone permission denied"
```bash
✅ iOS: Info.plist'e NSMicrophoneUsageDescription ekle
✅ Android: Runtime permissions ver
✅ Uygulamayı yeniden başlat
```

### ❌ "Audio file format not supported"
```bash
✅ WAV formatı kullan (mp3 değil)
✅ Sample rate: 44100 Hz
✅ FFmpeg ile dönüştür:
   ffmpeg -i input.mp3 -acodec pcm_s16le -ar 44100 output.wav
```

### ❌ Android emulator localhost'a bağlanamıyor
```bash
✅ URL'yi değiştir:
   'http://10.0.2.2:5000'  ← Emulator'dan host'a
```

---

## 🎯 Sonraki Adımlar

### Phase 1: Temel Test
- [ ] Backend ayağa kalktı mı?
- [ ] Ses kaydı yapılabiliyor mu?
- [ ] API response geliyor mu?
- [ ] Sonuç ekranı görünüyor mu?

### Phase 2: İnce Ayarlar
- [ ] Referans ses dosyaları hazır mı?
- [ ] Score weights doğru mu? (Telaffuz 40%, Med 35%, Harf 25%)
- [ ] Geri bildirim mesajları Türkçe doğru mu?
- [ ] UI renkleri ve fontlar tamam mı?

### Phase 3: Cloud Deploy
- [ ] Railway.app'a deploy et
- [ ] CORS ayarlarını kontrol et
- [ ] SSL sertifikasını ekle
- [ ] CDN'de ön bellek yapılandır

---

## 📞 KHK (Kısa Ayar Listesi)

| Ayar | Dosya | Satır | Değer |
|------|-------|-------|-------|
| Backend URL | `flutter_main_screen.dart` | ~24 | `'http://localhost:5000'` |
| Score ağırlıkları | `tecvid_backend.py` | ~285 | `0.4, 0.35, 0.25` |
| Mikrofon izni | `ios/Runner/Info.plist` | - | NSMicrophoneUsageDescription |
| Android SDK | `android/app/build.gradle` | ~8 | `compileSdkVersion 34` |
| Formant treshold | `tecvid_backend.py` | ~165 | LPC order = 12 |

---

## 🚀 Production Checklist

- [ ] Backend SSL/TLS etkin mi? (https://)
- [ ] API rate limiting var mı?
- [ ] Error handling ve logging implemented?
- [ ] User data privacy GDPR uyumlu mu?
- [ ] Ses dosyaları şifreli depolanıyor mu?
- [ ] Health check endpoint test edildi mi? (GET /health)
- [ ] Load testing yapıldı mı? (concurrent users)
- [ ] Monitoring ve alerting kurulu mu?

---

## 📚 Referans Saatler

| Görev | Tahmini Zaman |
|------|---|
| Python ortamı kurma | 2 dakika |
| Backend bağımlılıkları | 3-5 dakika (internet hızına bağlı) |
| Flutter pub get | 2-3 dakika |
| Test kaydı yapma | 1 dakika |
| Analiz işlemi | 2-3 saniye |
| **Toplam** | **~15 dakika** |

---

## 💡 İpuçları

✨ **Test Sürüsü Yapmak İçin:**
```bash
# Terminal 1: Backend
python tecvid_backend.py

# Terminal 2: Flutter
flutter run -d chrome  # Web test en hızlısı
```

✨ **Logging Aktif Etmek:**
```python
# tecvid_backend.py'nin başında:
import logging
logging.basicConfig(level=logging.DEBUG)
```

✨ **Mock Data İle Test:**
```bash
# Gerçek ses yerine test dosyası kullan
curl -X POST http://localhost:5000/analyze \
  -F "user_audio=@test_audio.wav" \
  -F "reference_audio=@reference.wav"
```

---

## ✅ Success Criteria

✓ Backend açılıyor
✓ Flutter uygulaması başlıyor
✓ Mikrofon erişimi yapılıyor
✓ Ses kaydı başarılı oluyor
✓ API request/response tamamlanıyor
✓ Skor hesaplanıyor (%0-100)
✓ UI sonuç gösteriyor
✓ Geri bildirim mesajları görünüyor

---

Başarılar Kral! 🎉

Soru varsa issue aç veya docs oku: SETUP_GUIDE.md
