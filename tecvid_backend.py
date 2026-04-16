"""
Tecvid Analiz Servisi - Python Backend
Flask + librosa + scipy ile akustik analiz
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import librosa
import numpy as np
from scipy import signal
from scipy.fft import fft
import os
import tempfile

app = Flask(__name__)
CORS(app)

# ============================================================================
# SES ÖZELLİKLERİ ÇIKARICI
# ============================================================================

class AudioAnalyzer:
    def __init__(self, audio_path: str, sr: int = 22050):
        """Ses dosyasını yükle ve temel bilgileri al"""
        self.y, self.sr = librosa.load(audio_path, sr=sr)
        self.duration_ms = int(len(self.y) / self.sr * 1000)
        
    def extract_pitch(self):
        """Pitch deteksiyonu (Fundamental Frequency)"""
        # PYIN algoritması kullanarak pitch çıkarma
        f0, voiced_flag, voiced_probs = librosa.pyin(
            self.y,
            fmin=librosa.note_to_hz('C2'),
            fmax=librosa.note_to_hz('C7'),
            sr=self.sr
        )
        
        # NaN değerleri temizle
        f0_clean = f0[~np.isnan(f0)]
        
        if len(f0_clean) > 0:
            pitch_mean = float(np.mean(f0_clean))
            pitch_std = float(np.std(f0_clean))
            pitch_values = f0_clean.tolist()[:20]  # İlk 20 frame
        else:
            pitch_mean = 0
            pitch_std = 0
            pitch_values = []
            
        return {
            'mean_hz': pitch_mean,
            'std_hz': pitch_std,
            'values': pitch_values,
        }
    
    def extract_energy(self):
        """Ses enerjisi (loudness) analizi"""
        # STFT ile frame-based enerji
        D = librosa.stft(self.y)
        magnitude = np.abs(D)
        energy = np.sum(magnitude ** 2, axis=0)
        energy_normalized = energy / np.max(energy) if np.max(energy) > 0 else energy
        
        return {
            'mean': float(np.mean(energy_normalized)),
            'max': float(np.max(energy_normalized)),
            'min': float(np.min(energy_normalized)),
            'values': energy_normalized[:20].tolist(),  # İlk 20 frame
        }
    
    def extract_mfcc(self, n_mfcc: int = 13):
        """MFCC - Mel-Frequency Cepstral Coefficients (konuşma tanımada standart)"""
        mfcc = librosa.feature.mfcc(y=self.y, sr=self.sr, n_mfcc=n_mfcc)
        mfcc_mean = np.mean(mfcc, axis=1).tolist()
        return {
            'mean_coefficients': mfcc_mean,
            'n_coefficients': n_mfcc,
        }
    
    def extract_formants(self):
        """
        Formant frekansları çıkarma (sesli harflerin kimliği)
        Formant 1 (F1): Çene yüksekliği
        Formant 2 (F2): Dil konumu (ön-arka)
        Formant 3 (F3): Dudak yuvarlama
        """
        # LPC (Linear Predictive Coding) ile formant tahmin
        # Ses bölütlenmesi: yüksek enerji bölgeleri
        S = librosa.feature.melspectrogram(y=self.y, sr=self.sr)
        energy_per_frame = np.mean(S, axis=0)
        
        # En yüksek enerji framelarını seç (vokal bölgeleri)
        threshold = np.mean(energy_per_frame) + np.std(energy_per_frame)
        vocal_frames = np.where(energy_per_frame > threshold)[0]
        
        formants = {
            'f1_hz': 0,
            'f2_hz': 0,
            'f3_hz': 0,
            'confidence': 0.0
        }
        
        if len(vocal_frames) > 0:
            # Vokal bölgesinin ortasını al
            mid_frame = vocal_frames[len(vocal_frames) // 2]
            start_sample = int(mid_frame * len(self.y) / len(energy_per_frame))
            end_sample = min(start_sample + self.sr // 4, len(self.y))  # 250ms pencere
            
            segment = self.y[start_sample:end_sample]
            
            # LPC analizi (12. derece)
            lpc_order = 12
            try:
                a = librosa.lpc(segment, order=lpc_order)
                
                # Roots hesapla
                roots = np.roots(a)
                angles = np.angle(roots)
                
                # Kararlı roots seç (magnitude < 1)
                freqs = angles * self.sr / (2 * np.pi)
                freqs = freqs[freqs > 0]
                freqs = np.sort(freqs)
                
                # İlk 3 formantı al
                if len(freqs) >= 3:
                    formants['f1_hz'] = int(freqs[0])
                    formants['f2_hz'] = int(freqs[1])
                    formants['f3_hz'] = int(freqs[2])
                    formants['confidence'] = 0.85
                elif len(freqs) >= 2:
                    formants['f1_hz'] = int(freqs[0])
                    formants['f2_hz'] = int(freqs[1])
                    formants['confidence'] = 0.70
            except Exception as e:
                print(f"LPC hatası: {e}")
        
        return formants
    
    def extract_zero_crossing_rate(self):
        """Sıfır Geçiş Oranı (titreşim, periyodiklik göstergesi)"""
        zcr = librosa.feature.zero_crossing_rate(self.y)[0]
        return {
            'mean': float(np.mean(zcr)),
            'std': float(np.std(zcr)),
            'values': zcr[:20].tolist(),
        }
    
    def extract_spectral_centroid(self):
        """Spektral Merkez (ortalama frekans)"""
        centroid = librosa.feature.spectral_centroid(y=self.y, sr=self.sr)[0]
        return {
            'mean_hz': float(np.mean(centroid)),
            'std_hz': float(np.std(centroid)),
            'values': centroid[:20].tolist(),
        }
    
    def extract_all_features(self):
        """Tüm özellikleri bir çıkışta topla"""
        return {
            'duration_ms': self.duration_ms,
            'pitch': self.extract_pitch(),
            'energy': self.extract_energy(),
            'mfcc': self.extract_mfcc(),
            'formants': self.extract_formants(),
            'zero_crossing_rate': self.extract_zero_crossing_rate(),
            'spectral_centroid': self.extract_spectral_centroid(),
        }

# ============================================================================
# TECVID KARŞILAŞTIRMA MOTORU
# ============================================================================

class TecvidComparator:
    @staticmethod
    def calculate_telaffuz_score(user_features: dict, ref_features: dict) -> dict:
        """Telaffuz kalitesi (pitch + tempo + clarity)"""
        score = 100.0
        pitch_error = 0.0
        
        # Pitch karşılaştırması
        user_pitch = user_features['pitch']['mean_hz']
        ref_pitch = ref_features['pitch']['mean_hz']
        
        if user_pitch > 0 and ref_pitch > 0:
            pitch_error = abs(user_pitch - ref_pitch) / ref_pitch
            score -= pitch_error * 20  # 0-20 puan
        
        # Enerji (clarity) karşılaştırması
        user_energy = user_features['energy']['mean']
        ref_energy = ref_features['energy']['mean']
        
        if user_energy > 0 and ref_energy > 0:
            energy_error = abs(user_energy - ref_energy) / ref_energy
            score -= energy_error * 15  # 0-15 puan
        
        score = max(0, min(100, score))
        
        return {
            'score': int(score),
            'level': TecvidComparator._get_level(score),
            'pitch_accuracy': int(100 - (pitch_error * 100)),
            'clarity': int(user_energy * 100) if user_energy > 0 else 0,
        }
    
    @staticmethod
    def calculate_med_score(user_features: dict, ref_features: dict) -> dict:
        """Med okunuşu (medenning) analizi"""
        score = 100.0
        
        # Süre karşılaştırması
        user_duration = user_features['duration_ms']
        ref_duration = ref_features['duration_ms']
        
        if ref_duration > 0:
            duration_ratio = user_duration / ref_duration
            
            # İdeal med oranı: 1.5-2.5x
            if duration_ratio < 1.3 or duration_ratio > 2.8:
                score -= 25
            elif duration_ratio < 1.5 or duration_ratio > 2.5:
                score -= 10
        
        # Formant stabilitesi (vokal kalitesi)
        user_formants = user_features['formants']
        ref_formants = ref_features['formants']
        
        if user_formants['f1_hz'] > 0 and ref_formants['f1_hz'] > 0:
            f1_error = abs(user_formants['f1_hz'] - ref_formants['f1_hz']) / ref_formants['f1_hz']
            score -= f1_error * 10
        
        score = max(0, min(100, score))
        
        return {
            'score': int(score),
            'level': TecvidComparator._get_level(score),
            'duration_ratio': round(duration_ratio if ref_duration > 0 else 0, 2),
            'vocal_quality': int(score * 0.6),
        }
    
    @staticmethod
    def calculate_harf_score(user_features: dict, ref_features: dict) -> dict:
        """Harf-sihah analizi (doğru noktadan çıkış)"""
        score = 100.0
        centroid_error = 0.0
        
        # Spektral karşılaştırma
        user_zcr = user_features['zero_crossing_rate']['mean']
        ref_zcr = ref_features['zero_crossing_rate']['mean']
        
        if ref_zcr > 0:
            zcr_error = abs(user_zcr - ref_zcr) / ref_zcr
            score -= zcr_error * 25
        
        user_centroid = user_features['spectral_centroid']['mean_hz']
        ref_centroid = ref_features['spectral_centroid']['mean_hz']
        
        if ref_centroid > 0:
            centroid_error = abs(user_centroid - ref_centroid) / ref_centroid
            score -= centroid_error * 20
        
        # MFCC benzerliği
        user_mfcc = np.array(user_features['mfcc']['mean_coefficients'])
        ref_mfcc = np.array(ref_features['mfcc']['mean_coefficients'])
        mfcc_distance = np.linalg.norm(user_mfcc - ref_mfcc)
        score -= min(15, mfcc_distance)
        
        score = max(0, min(100, score))
        
        return {
            'score': int(score),
            'level': TecvidComparator._get_level(score),
            'articulation': int(score * 0.8),
            'spectral_match': int((100 - (centroid_error * 100))),
        }
    
    @staticmethod
    def _get_level(score: float) -> str:
        if score >= 85:
            return 'mükemmel'
        elif score >= 70:
            return 'iyi'
        else:
            return 'geliştirilmeli'
    
    @staticmethod
    def calculate_total_score(telaffuz: dict, med: dict, harf: dict) -> int:
        """Ağırlıklandırılmış toplam skor"""
        weighted = (
            telaffuz['score'] * 0.4 +
            med['score'] * 0.35 +
            harf['score'] * 0.25
        )
        return int(weighted)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/analyze', methods=['POST'])
def analyze_audio():
    """
    POST /analyze
    Body: multipart/form-data
        - user_audio: ses dosyası (kullanıcı)
        - reference_audio: ses dosyası (referans/örnek)
    """
    try:
        if 'user_audio' not in request.files or 'reference_audio' not in request.files:
            return jsonify({'error': 'user_audio ve reference_audio gerekli'}), 400
        
        user_file = request.files['user_audio']
        ref_file = request.files['reference_audio']
        
        # Temp dosyalara kaydet
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as user_tmp:
            user_file.save(user_tmp.name)
            user_path = user_tmp.name
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as ref_tmp:
            ref_file.save(ref_tmp.name)
            ref_path = ref_tmp.name
        
        try:
            # Analiz et
            user_analyzer = AudioAnalyzer(user_path)
            ref_analyzer = AudioAnalyzer(ref_path)
            
            user_features = user_analyzer.extract_all_features()
            ref_features = ref_analyzer.extract_all_features()
            
            # Skorları hesapla
            telaffuz = TecvidComparator.calculate_telaffuz_score(user_features, ref_features)
            med = TecvidComparator.calculate_med_score(user_features, ref_features)
            harf = TecvidComparator.calculate_harf_score(user_features, ref_features)
            
            total_score = TecvidComparator.calculate_total_score(telaffuz, med, harf)
            
            # Geri bildirim oluştur
            notes = []
            if telaffuz['score'] < 70:
                notes.append('💬 Telaffuz: Pitch ve hız ayarını gözden geçir')
            elif telaffuz['score'] < 85:
                notes.append('💬 Telaffuz: Clarity biraz daha artırılabilir')
            else:
                notes.append('✅ Telaffuz: Çok iyi!')
            
            if med['score'] < 70:
                notes.append('📏 Med: Med harfleri daha uzun okumaya özen göster')
            elif med['score'] < 85:
                notes.append('📏 Med: Med harfleri biraz daha uzatılabilir')
            else:
                notes.append('✅ Med: Mükemmel!')
            
            if harf['score'] < 70:
                notes.append('🗣️ Harf: Harfleri daha net ve doğru noktadan çıkart')
            elif harf['score'] < 85:
                notes.append('🗣️ Harf: Artikülasyon biraz daha keskinleştirilebilir')
            else:
                notes.append('✅ Harf: Mükemmel!')
            
            return jsonify({
                'success': True,
                'totalScore': total_score,
                'telaffuz': {
                    'score': telaffuz['score'],
                    'level': telaffuz['level'],
                    'details': {
                        'pitchAccuracy': telaffuz['pitch_accuracy'],
                        'clarity': telaffuz['clarity'],
                    }
                },
                'med': {
                    'score': med['score'],
                    'level': med['level'],
                    'details': {
                        'durationRatio': med['duration_ratio'],
                        'vocalQuality': med['vocal_quality'],
                    }
                },
                'harf': {
                    'score': harf['score'],
                    'level': harf['level'],
                    'details': {
                        'articulation': harf['articulation'],
                        'spectralMatch': harf['spectral_match'],
                    }
                },
                'notes': notes,
                'userFeatures': user_features,  # Hata ayıklama için
                'referenceFeatures': ref_features,
            }), 200
            
        finally:
            # Temp dosyaları temizle
            os.unlink(user_path)
            os.unlink(ref_path)
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

# ============================================================================
# BAŞLAT
# ============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
