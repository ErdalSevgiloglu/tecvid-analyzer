# TECVID ANALYZER - KURULUM VE ENTEGRASYON KILAVUZU

## 📋 GENEL BAKIŞ

Tecvid Analyzer sistemi 3 bileşenden oluşur:
1. **Flutter Mobile App** - Kullanıcı arayüzü ve ses kaydı
2. **Python Flask Backend** - Ses analizi ve skorlama
3. **Reference Audio Files** - Örnek ses dosyaları

---

## 1️⃣ FLUTTER UYGULAMASI KURULUMU

### pubspec.yaml Bağımlılıkları

```yaml
dependencies:
  flutter:
    sdk: flutter
  
  # Ses Kaydı
  record: ^5.0.0
  
  # Dosya Yönetimi
  path_provider: ^2.1.0
  
  # HTTP İstekleri
  http: ^1.1.0
  
  # JSON İşleme (zaten built-in)
  
dev_dependencies:
  flutter_test:
    sdk: flutter
```

### Pubspec Yükleme

```bash
cd tecvid_analyzer_app
flutter pub get
```

### iOS Ayarları (iOS 14.0+)

`ios/Podfile` dosyasında:
```ruby
post_install do |installer|
  installer.pods_project.targets.each do |target|
    flutter_additional_ios_build_settings(target)
    target.build_configurations.each do |config|
      config.build_settings['GCC_PREPROCESSOR_DEFINITIONS'] ||= [
        '$(inherited)',
        'PERMISSION_MICROPHONE=1',
      ]
    end
  end
end
```

`ios/Runner/Info.plist` dosyasına:
```xml
<key>NSMicrophoneUsageDescription</key>
<string>Kur'an tilavetinizi analiz etmek için mikrofona ihtiyacımız var</string>
```

### Android Ayarları

`android/app/src/main/AndroidManifest.xml` dosyasına:
```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.INTERNET" />
```

`android/app/build.gradle` dosyasında:
```gradle
android {
    compileSdkVersion 34
    
    defaultConfig {
        minSdkVersion 21
        targetSdkVersion 34
    }
}
```

---

## 2️⃣ PYTHON FLASK BACKEND KURULUMU

### Gereksinimler

```bash
pip install -r requirements.txt
```

### requirements.txt

```
Flask==2.3.0
Flask-CORS==4.0.0
librosa==0.10.0
numpy==1.24.0
scipy==1.11.0
soundfile==0.12.1
```

### Detaylı Kurulum (macOS/Linux)

```bash
# Virtual environment oluştur
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# Windows: venv\Scripts\activate

# Bağımlılıkları yükle
pip install Flask Flask-CORS librosa numpy scipy soundfile

# Backend'i çalıştır
python tecvid_backend.py
```

### Windows Kurulumu

FFmpeg gerekli:
```bash
# Chocolatey ile
choco install ffmpeg

# Veya manuel olarak: https://ffmpeg.org/download.html
```

### Geliştirme Sunucusu Başlatma

```bash
# Terminal 1: Backend
python tecvid_backend.py
# Output: Running on http://0.0.0.0:5000

# Terminal 2: Flutter (cihazda test için)
flutter run --device-id emulator-5554
# Veya fiziksel cihaz: flutter devices
```

---

## 3️⃣ REFERANS SES DOSYALARI

### Dosya Organizasyonu

```
flutter_app/
├── assets/
│   └── audios/
│       ├── bismillah_reference.wav
│       ├── alhamdulillah_reference.wav
│       └── ...
├── pubspec.yaml
└── ...
```

### pubspec.yaml'a Ekleme

```yaml
flutter:
  assets:
    - assets/audios/
```

### Referans Ses Türleri

1. **Bismillah** (بسم الله الرحمن الرحيم)
   - Süre: 2-3 saniye
   - Pitch: 130-150 Hz
   - Mikrofon: Kaliteli profesyonel mikrofon

2. **Harfler** (Müfrete harfler)
   - Her harf ayrı ayrı
   - Net telaffuz ile

3. **Med Örnekleri**
   - Doğru med okunuşu (1.5-2.5x)
   - Hatalı med (çok kısa/çok uzun)

### Ses Dosyası Hazırlama

FFmpeg ile:
```bash
# WAV formatına çevir
ffmpeg -i original.mp3 -acodec pcm_s16le -ar 44100 bismillah_reference.wav

# Ses kalitesini kontrol et
ffprobe -v error -show_entries format=duration,sample_rate bismillah_reference.wav
```

---

## 4️⃣ BACKEND-FLUTTER ENTEGRASYON

### API Endpoint Yapısı

**POST** `/analyze`

**Request:**
```json
Content-Type: multipart/form-data

- user_audio: [binary WAV file]
- reference_audio: [binary WAV file]
```

**Response:**
```json
{
  "success": true,
  "totalScore": 82,
  "telaffuz": {
    "score": 80,
    "level": "iyi",
    "details": {
      "pitchAccuracy": 85,
      "clarity": 75
    }
  },
  "med": {
    "score": 85,
    "level": "iyi",
    "details": {
      "durationRatio": 2.1,
      "vocalQuality": 80
    }
  },
  "harf": {
    "score": 82,
    "level": "iyi",
    "details": {
      "articulation": 80,
      "spectralMatch": 85
    }
  },
  "notes": [
    "✅ Telaffuz: Çok iyi!",
    "📏 Med: Mükemmel!",
    "✅ Harf: Biraz daha keskinleştirilebilir"
  ]
}
```

### Flutter'da Backend URL Ayarı

`flutter_main_screen.dart` dosyasında:

```dart
// Geliştirme (localhost)
static const String BACKEND_URL = 'http://localhost:5000';

// Üretim (cloud sunucusu)
static const String BACKEND_URL = 'https://api.tecvidanalyzer.com';

// Android emulator'dan localhost'a erişim
static const String BACKEND_URL = 'http://10.0.2.2:5000';
```

---

## 5️⃣ NETWORK KONFİGÜRASYONU

### iOS

`ios/Runner/Info.plist` dosyasına:
```xml
<key>NSLocalNetworkUsageDescription</key>
<string>Tecvid analizi için yerel ağa erişim gerekli</string>
<key>NSBonjourServices</key>
<array>
    <string>_services._tcp</string>
</array>
```

### Android

`android/app/src/main/AndroidManifest.xml` dosyasına:
```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
```

### CORS (Cross-Origin)

Backend'de zaten yapılmış:
```python
from flask_cors import CORS
CORS(app)
```

---

## 6️⃣ CLOUD DEĞİŞTİRME (AWS/GCP/Railway)

### Railway.app Deployment (Önerilen)

```bash
# 1. Railway.app'a kaydol: https://railway.app

# 2. Repository oluştur
git init
git add .
git commit -m "Tecvid Backend"

# 3. Railway CLI yükle
npm install -g @railway/cli
railway login
railway init

# 4. Deploy
railway up

# 5. Environment Variable (CORS)
railway variables set FLASK_ENV=production
```

### Docker ile Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tecvid_backend.py .

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "tecvid_backend:app"]
```

Başlatma:
```bash
docker build -t tecvid-backend .
docker run -p 5000:5000 tecvid-backend
```

---

## 7️⃣ HATA AYIKLAMA

### Common Issues

1. **"Connection refused" hatası**
   ```
   ❌ Backend çalışmıyor mu? 
   ✅ python tecvid_backend.py ile başlat
   
   ❌ Yanlış URL mu?
   ✅ Backend URL'sini kontrol et
   ```

2. **"Microphone permission denied"**
   ```
   ✅ iOS: Info.plist'te NSMicrophoneUsageDescription olduğundan emin ol
   ✅ Android: Runtime permissions kontrol et
   ```

3. **"Audio file format not supported"**
   ```
   ✅ WAV formatı kullan (mp3 değil)
   ✅ Sample rate: 44100 Hz
   ```

### Logging

Flutter'da:
```dart
print('Kayıt yolu: $_recordingPath');
print('Response: ${response.body}');
```

Python'da:
```python
@app.before_request
def log_request():
    print(f"Request: {request.method} {request.path}")

import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 8️⃣ TEST AYILLARI

### Cypress E2E Test (Flutter için)

```bash
flutter test test/tecvid_analyzer_test.dart
```

### Python Backend Test

```python
# test_tecvid.py
import requests
import os

def test_analyze():
    files = {
        'user_audio': open('test_audio.wav', 'rb'),
        'reference_audio': open('reference.wav', 'rb'),
    }
    response = requests.post('http://localhost:5000/analyze', files=files)
    assert response.status_code == 200
    data = response.json()
    assert 'totalScore' in data
    assert data['totalScore'] >= 0 and data['totalScore'] <= 100

if __name__ == '__main__':
    test_analyze()
    print("✅ Test passed!")
```

Çalıştırma:
```bash
pip install requests
python test_tecvid.py
```

---

## 9️⃣ TUNING VE OPTİMİZASYON

### Model Ağırlıkları (tecvid_backend.py)

```python
# Şu anki ağırlıklar:
# Telaffuz: %40
# Med: %35
# Harf: %25

# Harf daha önemli için:
total_score = (
    telaffuz['score'] * 0.35 +
    med['score'] * 0.25 +
    harf['score'] * 0.40  # ↑
)
```

### Threshold Ayarları

```python
# Telaffuz kalitesi threshold'ü
if score > 85:        # mükemmel
    level = 'mükemmel'
elif score > 70:      # iyi
    level = 'iyi'
else:                 # geliştirilmeli
    level = 'geliştirilmeli'
```

---

## 🔟 CANLIYA ALMA CHECKL
İST

- [ ] Backend server çalışıyor mu?
- [ ] Flutter uygulaması backend URL'sine bağlanabiliyor mu?
- [ ] Referans ses dosyaları doğru yüklenmiş mi?
- [ ] İOS mikrofon izni var mı?
- [ ] Android runtime permissions var mı?
- [ ] Ses dosyaları WAV formatında mı?
- [ ] Backend API dönen verilerin formatı doğru mu?
- [ ] Skor hesaplama formülü test edildi mi?
- [ ] Geri bildirim mesajları Türkçe doğru mu?
- [ ] Cloud deployment test edildi mi (varsa)?

---

## 📞 DESTEK

```
Error: ModuleNotFoundError: No module named 'librosa'
→ pip install librosa

Error: No audio input device found
→ Cihazın mikrofonu kontrol et, permissions ver

Error: CORS error
→ Backend'de CORS(app) ekleyin
```

Başarılar Kral! 🚀
