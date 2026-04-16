"""
Tecvid Analiz Servisi - Python Backend
soundfile + numpy ile akustik analiz (librosa bağımlılığı yok)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import soundfile as sf
import os
import tempfile

app = Flask(__name__)
CORS(app)

# ============================================================================
# SES ÖZELLİKLERİ ÇIKARICI
# ============================================================================

class AudioAnalyzer:
    def __init__(self, audio_path: str):
        self.y, self.sr = sf.read(audio_path, always_2d=False)
        # Stereo ise mono'ya çevir
        if self.y.ndim > 1:
            self.y = np.mean(self.y, axis=1)
        self.y = self.y.astype(np.float32)
        self.duration_ms = int(len(self.y) / self.sr * 1000)

    def extract_pitch(self):
        """Basit pitch tahmini (zero-crossing tabanlı)"""
        frame_size = int(self.sr * 0.025)  # 25ms frame
        hop = int(self.sr * 0.010)         # 10ms hop
        pitches = []

        for i in range(0, len(self.y) - frame_size, hop):
            frame = self.y[i:i + frame_size]
            # Autocorrelation ile pitch
            corr = np.correlate(frame, frame, mode='full')
            corr = corr[len(corr)//2:]
            # Min lag: 50Hz, max lag: 400Hz
            min_lag = int(self.sr / 400)
            max_lag = int(self.sr / 50)
            if max_lag < len(corr):
                peak = np.argmax(corr[min_lag:max_lag]) + min_lag
                if corr[peak] > 0.3 * corr[0]:
                    pitches.append(self.sr / peak)

        if pitches:
            return {
                'mean_hz': float(np.mean(pitches)),
                'std_hz': float(np.std(pitches)),
                'values': pitches[:20],
            }
        return {'mean_hz': 0.0, 'std_hz': 0.0, 'values': []}

    def extract_energy(self):
        """RMS enerji analizi"""
        frame_size = int(self.sr * 0.025)
        hop = int(self.sr * 0.010)
        energies = []

        for i in range(0, len(self.y) - frame_size, hop):
            frame = self.y[i:i + frame_size]
            rms = np.sqrt(np.mean(frame ** 2))
            energies.append(float(rms))

        if not energies:
            return {'mean': 0.0, 'max': 0.0, 'min': 0.0, 'values': []}

        max_e = max(energies) or 1.0
        normalized = [e / max_e for e in energies]
        return {
            'mean': float(np.mean(normalized)),
            'max': float(np.max(normalized)),
            'min': float(np.min(normalized)),
            'values': normalized[:20],
        }

    def extract_zero_crossing_rate(self):
        """Sıfır geçiş oranı"""
        frame_size = int(self.sr * 0.025)
        hop = int(self.sr * 0.010)
        zcrs = []

        for i in range(0, len(self.y) - frame_size, hop):
            frame = self.y[i:i + frame_size]
            zcr = np.sum(np.abs(np.diff(np.sign(frame)))) / (2 * len(frame))
            zcrs.append(float(zcr))

        return {
            'mean': float(np.mean(zcrs)) if zcrs else 0.0,
            'std': float(np.std(zcrs)) if zcrs else 0.0,
            'values': zcrs[:20],
        }

    def extract_spectral_centroid(self):
        """Spektral merkez (FFT tabanlı)"""
        frame_size = int(self.sr * 0.025)
        hop = int(self.sr * 0.010)
        centroids = []
        freqs = np.fft.rfftfreq(frame_size, d=1.0/self.sr)

        for i in range(0, len(self.y) - frame_size, hop):
            frame = self.y[i:i + frame_size]
            magnitude = np.abs(np.fft.rfft(frame))
            total = np.sum(magnitude)
            if total > 0:
                centroid = float(np.sum(freqs * magnitude) / total)
                centroids.append(centroid)

        return {
            'mean_hz': float(np.mean(centroids)) if centroids else 0.0,
            'std_hz': float(np.std(centroids)) if centroids else 0.0,
            'values': centroids[:20],
        }

    def extract_mfcc_simple(self, n_mfcc=13):
        """Basit MFCC benzeri spektral özellikler"""
        frame_size = int(self.sr * 0.025)
        hop = int(self.sr * 0.010)
        all_features = []

        for i in range(0, len(self.y) - frame_size, hop):
            frame = self.y[i:i + frame_size]
            magnitude = np.abs(np.fft.rfft(frame))
            # Log spektrum
            log_spec = np.log(magnitude + 1e-10)
            # DCT benzeri özellikler
            features = log_spec[:n_mfcc]
            all_features.append(features)

        if all_features:
            mean_features = np.mean(all_features, axis=0)
            return {'mean_coefficients': mean_features.tolist()}
        return {'mean_coefficients': [0.0] * n_mfcc}

    def extract_formants(self):
        """Basit formant tahmini"""
        frame_size = int(self.sr * 0.025)
        mid = len(self.y) // 2
        frame = self.y[mid:mid + frame_size]
        magnitude = np.abs(np.fft.rfft(frame))
        freqs = np.fft.rfftfreq(frame_size, d=1.0/self.sr)

        # Yerel maksimumları bul
        peaks = []
        for j in range(1, len(magnitude) - 1):
            if magnitude[j] > magnitude[j-1] and magnitude[j] > magnitude[j+1]:
                if freqs[j] > 100:
                    peaks.append((magnitude[j], freqs[j]))

        peaks.sort(reverse=True)
        f1 = int(peaks[0][1]) if len(peaks) > 0 else 0
        f2 = int(peaks[1][1]) if len(peaks) > 1 else 0
        f3 = int(peaks[2][1]) if len(peaks) > 2 else 0

        return {'f1_hz': f1, 'f2_hz': f2, 'f3_hz': f3, 'confidence': 0.7}

    def extract_all_features(self):
        return {
            'duration_ms': self.duration_ms,
            'pitch': self.extract_pitch(),
            'energy': self.extract_energy(),
            'mfcc': self.extract_mfcc_simple(),
            'formants': self.extract_formants(),
            'zero_crossing_rate': self.extract_zero_crossing_rate(),
            'spectral_centroid': self.extract_spectral_centroid(),
        }

# ============================================================================
# TECVID KARŞILAŞTIRMA MOTORU
# ============================================================================

class TecvidComparator:
    @staticmethod
    def _get_level(score: float) -> str:
        if score >= 85:
            return 'mükemmel'
        elif score >= 70:
            return 'iyi'
        return 'geliştirilmeli'

    @staticmethod
    def calculate_telaffuz_score(user: dict, ref: dict) -> dict:
        score = 100.0
        pitch_error = 0.0

        u_pitch = user['pitch']['mean_hz']
        r_pitch = ref['pitch']['mean_hz']
        if u_pitch > 0 and r_pitch > 0:
            pitch_error = abs(u_pitch - r_pitch) / r_pitch
            score -= pitch_error * 20

        u_energy = user['energy']['mean']
        r_energy = ref['energy']['mean']
        if u_energy > 0 and r_energy > 0:
            energy_error = abs(u_energy - r_energy) / r_energy
            score -= energy_error * 15

        score = max(0, min(100, score))
        return {
            'score': int(score),
            'level': TecvidComparator._get_level(score),
            'pitch_accuracy': int(max(0, 100 - pitch_error * 100)),
            'clarity': int(u_energy * 100),
        }

    @staticmethod
    def calculate_med_score(user: dict, ref: dict) -> dict:
        score = 100.0
        duration_ratio = 1.0

        r_dur = ref['duration_ms']
        if r_dur > 0:
            duration_ratio = user['duration_ms'] / r_dur
            if duration_ratio < 1.3 or duration_ratio > 2.8:
                score -= 25
            elif duration_ratio < 1.5 or duration_ratio > 2.5:
                score -= 10

        u_f1 = user['formants']['f1_hz']
        r_f1 = ref['formants']['f1_hz']
        if u_f1 > 0 and r_f1 > 0:
            f1_error = abs(u_f1 - r_f1) / r_f1
            score -= f1_error * 10

        score = max(0, min(100, score))
        return {
            'score': int(score),
            'level': TecvidComparator._get_level(score),
            'duration_ratio': round(duration_ratio, 2),
            'vocal_quality': int(score * 0.6),
        }

    @staticmethod
    def calculate_harf_score(user: dict, ref: dict) -> dict:
        score = 100.0
        centroid_error = 0.0

        r_zcr = ref['zero_crossing_rate']['mean']
        if r_zcr > 0:
            zcr_error = abs(user['zero_crossing_rate']['mean'] - r_zcr) / r_zcr
            score -= zcr_error * 25

        r_cent = ref['spectral_centroid']['mean_hz']
        if r_cent > 0:
            centroid_error = abs(user['spectral_centroid']['mean_hz'] - r_cent) / r_cent
            score -= centroid_error * 20

        u_mfcc = np.array(user['mfcc']['mean_coefficients'])
        r_mfcc = np.array(ref['mfcc']['mean_coefficients'])
        mfcc_dist = float(np.linalg.norm(u_mfcc - r_mfcc))
        score -= min(15, mfcc_dist)

        score = max(0, min(100, score))
        return {
            'score': int(score),
            'level': TecvidComparator._get_level(score),
            'articulation': int(score * 0.8),
            'spectral_match': int(max(0, 100 - centroid_error * 100)),
        }

    @staticmethod
    def calculate_total_score(telaffuz: dict, med: dict, harf: dict) -> int:
        return int(telaffuz['score'] * 0.4 + med['score'] * 0.35 + harf['score'] * 0.25)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/analyze', methods=['POST'])
def analyze_audio():
    try:
        if 'user_audio' not in request.files or 'reference_audio' not in request.files:
            return jsonify({'error': 'user_audio ve reference_audio gerekli'}), 400

        user_file = request.files['user_audio']
        ref_file = request.files['reference_audio']

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as u_tmp:
            user_file.save(u_tmp.name)
            user_path = u_tmp.name

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as r_tmp:
            ref_file.save(r_tmp.name)
            ref_path = r_tmp.name

        try:
            user_features = AudioAnalyzer(user_path).extract_all_features()
            ref_features = AudioAnalyzer(ref_path).extract_all_features()

            telaffuz = TecvidComparator.calculate_telaffuz_score(user_features, ref_features)
            med = TecvidComparator.calculate_med_score(user_features, ref_features)
            harf = TecvidComparator.calculate_harf_score(user_features, ref_features)
            total = TecvidComparator.calculate_total_score(telaffuz, med, harf)

            notes = []
            for label, data, icon in [
                ('Telaffuz', telaffuz, '💬'),
                ('Med', med, '📏'),
                ('Harf', harf, '🗣️'),
            ]:
                s = data['score']
                if s < 70:
                    notes.append(f'{icon} {label}: Daha fazla pratik gerekiyor')
                elif s < 85:
                    notes.append(f'{icon} {label}: Biraz daha geliştirilebilir')
                else:
                    notes.append(f'✅ {label}: Mükemmel!')

            return jsonify({
                'success': True,
                'totalScore': total,
                'telaffuz': {'score': telaffuz['score'], 'level': telaffuz['level']},
                'med': {'score': med['score'], 'level': med['level']},
                'harf': {'score': harf['score'], 'level': harf['level']},
                'notes': notes,
            }), 200

        finally:
            os.unlink(user_path)
            os.unlink(ref_path)

    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
