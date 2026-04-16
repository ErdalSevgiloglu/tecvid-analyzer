"""
Tecvid Analiz Servisi
DTW + spektral analiz ile gerçekçi tecvid değerlendirmesi
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
# SES YÜKLEME
# ============================================================================

def load_audio(path: str, target_sr: int = 16000):
    """Ses dosyasını yükle, mono + resample"""
    y, sr = sf.read(path, always_2d=False)
    if y.ndim > 1:
        y = np.mean(y, axis=1)
    y = y.astype(np.float64)

    # Basit resample (integer oran)
    if sr != target_sr:
        ratio = target_sr / sr
        new_len = int(len(y) * ratio)
        indices = np.linspace(0, len(y) - 1, new_len)
        y = np.interp(indices, np.arange(len(y)), y)

    return y, target_sr

# ============================================================================
# SPEKTRAL ÖZELLİK ÇIKARIMI
# ============================================================================

def compute_frames(y, sr, frame_ms=25, hop_ms=10):
    frame_size = int(sr * frame_ms / 1000)
    hop_size = int(sr * hop_ms / 1000)
    frames = []
    for i in range(0, len(y) - frame_size, hop_size):
        frames.append(y[i:i + frame_size])
    return np.array(frames), frame_size, hop_size

def mel_filterbank(sr, n_fft, n_mels=26, fmin=80, fmax=7600):
    """Mel filtre bankası"""
    def hz_to_mel(hz): return 2595 * np.log10(1 + hz / 700)
    def mel_to_hz(mel): return 700 * (10 ** (mel / 2595) - 1)

    mel_min = hz_to_mel(fmin)
    mel_max = hz_to_mel(fmax)
    mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
    hz_points = mel_to_hz(mel_points)
    bin_points = np.floor((n_fft + 1) * hz_points / sr).astype(int)

    filterbank = np.zeros((n_mels, n_fft // 2 + 1))
    for m in range(1, n_mels + 1):
        f_m_minus = bin_points[m - 1]
        f_m = bin_points[m]
        f_m_plus = bin_points[m + 1]
        for k in range(f_m_minus, f_m):
            if f_m != f_m_minus:
                filterbank[m - 1, k] = (k - f_m_minus) / (f_m - f_m_minus)
        for k in range(f_m, f_m_plus):
            if f_m_plus != f_m:
                filterbank[m - 1, k] = (f_m_plus - k) / (f_m_plus - f_m)
    return filterbank

def extract_mfcc(y, sr, n_mfcc=13, n_mels=26):
    """MFCC çıkar — her frame için"""
    frames, frame_size, _ = compute_frames(y, sr)
    if len(frames) == 0:
        return np.zeros((1, n_mfcc))

    window = np.hanning(frame_size)
    fb = mel_filterbank(sr, frame_size, n_mels)
    mfccs = []

    for frame in frames:
        if len(frame) < frame_size:
            continue
        windowed = frame * window
        spectrum = np.abs(np.fft.rfft(windowed)) ** 2
        mel_energy = np.dot(fb, spectrum)
        log_mel = np.log(mel_energy + 1e-10)
        # DCT
        n = len(log_mel)
        dct = np.array([
            np.sum(log_mel * np.cos(np.pi * k * (np.arange(n) + 0.5) / n))
            for k in range(n_mfcc)
        ])
        mfccs.append(dct)

    return np.array(mfccs)  # shape: (n_frames, n_mfcc)

def extract_pitch_sequence(y, sr):
    """Autocorrelation ile frame bazlı pitch"""
    frames, frame_size, _ = compute_frames(y, sr)
    pitches = []
    min_lag = int(sr / 400)  # 400 Hz max
    max_lag = int(sr / 60)   # 60 Hz min

    for frame in frames:
        if len(frame) < frame_size:
            pitches.append(0.0)
            continue
        corr = np.correlate(frame, frame, mode='full')
        corr = corr[len(corr) // 2:]
        if max_lag >= len(corr):
            pitches.append(0.0)
            continue
        segment = corr[min_lag:max_lag]
        peak_idx = np.argmax(segment)
        peak_val = segment[peak_idx]
        if corr[0] > 0 and peak_val / corr[0] > 0.25:
            pitches.append(sr / (peak_idx + min_lag))
        else:
            pitches.append(0.0)

    return np.array(pitches)

def extract_energy_sequence(y, sr):
    """Frame bazlı RMS enerji"""
    frames, _, _ = compute_frames(y, sr)
    return np.array([np.sqrt(np.mean(f ** 2)) for f in frames])

# ============================================================================
# DTW (Dynamic Time Warping)
# ============================================================================

def dtw_distance(seq1, seq2):
    """
    İki dizi arasında DTW mesafesi hesapla.
    seq1, seq2: (n_frames,) veya (n_frames, n_features)
    Normalize edilmiş mesafe döner (0=mükemmel, 1+=kötü)
    """
    n, m = len(seq1), len(seq2)
    if n == 0 or m == 0:
        return 1.0

    # Boyut uyumu
    if seq1.ndim == 1:
        seq1 = seq1.reshape(-1, 1)
        seq2 = seq2.reshape(-1, 1)

    # Bellek için downsample (max 200 frame)
    if n > 200:
        idx = np.linspace(0, n - 1, 200).astype(int)
        seq1 = seq1[idx]
        n = 200
    if m > 200:
        idx = np.linspace(0, m - 1, 200).astype(int)
        seq2 = seq2[idx]
        m = 200

    dtw = np.full((n + 1, m + 1), np.inf)
    dtw[0, 0] = 0

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = np.linalg.norm(seq1[i - 1] - seq2[j - 1])
            dtw[i, j] = cost + min(dtw[i-1, j], dtw[i, j-1], dtw[i-1, j-1])

    # Normalize: path uzunluğuna böl
    path_len = n + m
    return float(dtw[n, m]) / path_len

# ============================================================================
# SKORLAMA
# ============================================================================

def score_from_dtw(distance, sensitivity=3.0):
    """DTW mesafesini 0-100 skora çevir."""
    score = 100 * np.exp(-sensitivity * distance)
    return max(0, min(100, float(score)))

def get_level(score):
    if score >= 80:
        return 'mükemmel'
    elif score >= 60:
        return 'iyi'
    return 'geliştirilmeli'

def analyze(user_path, ref_path):
    user_y, sr = load_audio(user_path)
    ref_y, _   = load_audio(ref_path)

    user_dur = len(user_y) / sr * 1000  # ms
    ref_dur  = len(ref_y) / sr * 1000

    # --- MFCC (harf kalitesi + genel benzerlik) ---
    user_mfcc = extract_mfcc(user_y, sr)  # (frames, 13)
    ref_mfcc  = extract_mfcc(ref_y, sr)
    # --- MFCC normalize et önce ---
    if user_mfcc.shape[0] > 0 and ref_mfcc.shape[0] > 0:
        # Her katsayıyı std ile normalize et
        combined = np.vstack([user_mfcc, ref_mfcc])
        std = np.std(combined, axis=0) + 1e-8
        user_mfcc_n = user_mfcc / std
        ref_mfcc_n  = ref_mfcc / std
    else:
        user_mfcc_n, ref_mfcc_n = user_mfcc, ref_mfcc

    mfcc_dist = dtw_distance(user_mfcc_n, ref_mfcc_n)
    harf_score = score_from_dtw(mfcc_dist, sensitivity=2.0)

    # --- PITCH (telaffuz / makam) ---
    user_pitch = extract_pitch_sequence(user_y, sr)
    ref_pitch  = extract_pitch_sequence(ref_y, sr)
    # Sadece sesli bölgeler (pitch > 0)
    up = user_pitch[user_pitch > 0]
    rp = ref_pitch[ref_pitch > 0]
    if len(up) > 5 and len(rp) > 5:
        # Pitch'i normalize et (konuşmacı bağımsız)
        up_n = (up - np.mean(up)) / (np.std(up) + 1e-8)
        rp_n = (rp - np.mean(rp)) / (np.std(rp) + 1e-8)
        pitch_dist = dtw_distance(up_n, rp_n)
        telaffuz_score = score_from_dtw(pitch_dist, sensitivity=1.5)
    else:
        telaffuz_score = 60.0

    # --- SÜRE (med / uzatma) ---
    dur_ratio = user_dur / ref_dur if ref_dur > 0 else 1.0
    # İdeal: 0.65 - 1.45 arası
    if 0.65 <= dur_ratio <= 1.45:
        dur_score = 100.0
    elif 0.45 <= dur_ratio <= 1.7:
        deviation = max(abs(dur_ratio - 1.0) - 0.45, 0)
        dur_score = 100.0 - (deviation / 0.25) * 35
    else:
        deviation = abs(dur_ratio - 1.0)
        dur_score = max(0, 65 - (deviation - 0.7) * 80)

    # Enerji profili benzerliği (med harflerinin uzatılması)
    user_energy = extract_energy_sequence(user_y, sr)
    ref_energy  = extract_energy_sequence(ref_y, sr)
    energy_dist = dtw_distance(user_energy, ref_energy)
    energy_score = score_from_dtw(energy_dist, sensitivity=2.0)

    med_score = dur_score * 0.6 + energy_score * 0.4

    # --- TOPLAM ---
    total = int(telaffuz_score * 0.35 + med_score * 0.35 + harf_score * 0.30)

    # --- NOTLAR ---
    notes = []

    if telaffuz_score < 60:
        notes.append('💬 Telaffuz: Ses tonu ve ritim referanstan çok farklı')
    elif telaffuz_score < 80:
        notes.append('💬 Telaffuz: Pitch biraz daha referansa yaklaştırılabilir')
    else:
        notes.append('✅ Telaffuz: Çok iyi!')

    if dur_ratio < 0.75:
        notes.append(f'📏 Med: Çok kısa okudun (referansın %{int(dur_ratio*100)}\'i kadar)')
    elif dur_ratio > 1.5:
        notes.append(f'📏 Med: Çok uzun okudun (referansın %{int(dur_ratio*100)}\'i kadar)')
    elif med_score < 60:
        notes.append('📏 Med: Uzatma sürelerine dikkat et')
    elif med_score < 80:
        notes.append('📏 Med: Med harfleri biraz daha geliştirilebilir')
    else:
        notes.append('✅ Med: Mükemmel!')

    if harf_score < 60:
        notes.append('🗣️ Harf: Harflerin çıkış noktaları referanstan belirgin farklı')
    elif harf_score < 80:
        notes.append('🗣️ Harf: Artikülasyon geliştirilebilir')
    else:
        notes.append('✅ Harf: Mükemmel!')

    return {
        'totalScore': total,
        'telaffuz': {'score': int(telaffuz_score), 'level': get_level(telaffuz_score)},
        'med':      {'score': int(med_score),      'level': get_level(med_score)},
        'harf':     {'score': int(harf_score),     'level': get_level(harf_score)},
        'notes': notes,
        'debug': {
            'user_dur_ms': int(user_dur),
            'ref_dur_ms':  int(ref_dur),
            'dur_ratio':   round(dur_ratio, 2),
            'mfcc_dtw':    round(mfcc_dist, 4),
            'pitch_dtw':   round(pitch_dist if len(up) > 5 and len(rp) > 5 else -1, 4),
            'energy_dtw':  round(energy_dist, 4),
        }
    }

# ============================================================================
# API
# ============================================================================

@app.route('/analyze', methods=['POST'])
def analyze_audio():
    try:
        if 'user_audio' not in request.files or 'reference_audio' not in request.files:
            return jsonify({'error': 'user_audio ve reference_audio gerekli'}), 400

        user_file = request.files['user_audio']
        ref_file  = request.files['reference_audio']

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as u:
            user_file.save(u.name); user_path = u.name
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as r:
            ref_file.save(r.name);  ref_path  = r.name

        try:
            result = analyze(user_path, ref_path)
            result['success'] = True
            return jsonify(result), 200
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
