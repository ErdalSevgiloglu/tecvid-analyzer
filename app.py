"""
Tecvid Analiz Servisi
DTW + Whisper STT ile gerçekçi tecvid değerlendirmesi
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import soundfile as sf
import os
import tempfile

app = Flask(__name__)
CORS(app)

# Groq Whisper API (ücretsiz, sistem bağımlılığı yok)
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

# ============================================================================
# FATIHA AYETLERİ (beklenen metin)
# ============================================================================

FATIHA_TEXTS = {
    1: "بسم الله الرحمن الرحيم",
    2: "الحمد لله رب العالمين",
    3: "الرحمن الرحيم",
    4: "مالك يوم الدين",
    5: "إياك نعبد وإياك نستعين",
    6: "اهدنا الصراط المستقيم",
    7: "صراط الذين أنعمت عليهم غير المغضوب عليهم ولا الضالين",
}

# ============================================================================
# SES YÜKLEME
# ============================================================================

def load_audio(path: str, target_sr: int = 16000):
    y, sr = sf.read(path, always_2d=False)
    if y.ndim > 1:
        y = np.mean(y, axis=1)
    y = y.astype(np.float64)
    if sr != target_sr:
        new_len = int(len(y) * target_sr / sr)
        y = np.interp(np.linspace(0, len(y)-1, new_len), np.arange(len(y)), y)
    return y, target_sr

# ============================================================================
# ÖZELLİK ÇIKARIMI
# ============================================================================

def compute_frames(y, sr, frame_ms=25, hop_ms=10):
    fs = int(sr * frame_ms / 1000)
    hs = int(sr * hop_ms / 1000)
    return [y[i:i+fs] for i in range(0, len(y)-fs, hs)], fs

def mel_filterbank(sr, n_fft, n_mels=26, fmin=80, fmax=7600):
    def hz2mel(h): return 2595 * np.log10(1 + h/700)
    def mel2hz(m): return 700 * (10**(m/2595) - 1)
    mels = np.linspace(hz2mel(fmin), hz2mel(fmax), n_mels+2)
    bins = np.floor((n_fft+1) * mel2hz(mels) / sr).astype(int)
    fb = np.zeros((n_mels, n_fft//2+1))
    for m in range(1, n_mels+1):
        for k in range(bins[m-1], bins[m]):
            if bins[m] != bins[m-1]:
                fb[m-1, k] = (k - bins[m-1]) / (bins[m] - bins[m-1])
        for k in range(bins[m], bins[m+1]):
            if bins[m+1] != bins[m]:
                fb[m-1, k] = (bins[m+1] - k) / (bins[m+1] - bins[m])
    return fb

def extract_mfcc(y, sr, n_mfcc=13):
    frames, fs = compute_frames(y, sr)
    if not frames: return np.zeros((1, n_mfcc))
    win = np.hanning(fs)
    fb  = mel_filterbank(sr, fs)
    out = []
    for f in frames:
        if len(f) < fs: continue
        mag = np.abs(np.fft.rfft(f * win))**2
        mel = np.log(np.dot(fb, mag) + 1e-10)
        n   = len(mel)
        dct = np.array([np.sum(mel * np.cos(np.pi*k*(np.arange(n)+0.5)/n)) for k in range(n_mfcc)])
        out.append(dct)
    return np.array(out) if out else np.zeros((1, n_mfcc))

def extract_pitch(y, sr):
    frames, fs = compute_frames(y, sr)
    min_lag, max_lag = int(sr/400), int(sr/60)
    pitches = []
    for f in frames:
        if len(f) < fs: pitches.append(0.0); continue
        c = np.correlate(f, f, 'full')[len(f)-1:]
        if max_lag >= len(c): pitches.append(0.0); continue
        seg = c[min_lag:max_lag]
        pk  = np.argmax(seg)
        pitches.append(sr/(pk+min_lag) if c[0]>0 and seg[pk]/c[0]>0.25 else 0.0)
    return np.array(pitches)

def extract_energy(y, sr):
    frames, _ = compute_frames(y, sr)
    return np.array([np.sqrt(np.mean(f**2)) for f in frames])

# ============================================================================
# DTW
# ============================================================================

def dtw_distance(a, b):
    if a.ndim == 1: a = a.reshape(-1,1)
    if b.ndim == 1: b = b.reshape(-1,1)
    def ds(x):
        if len(x) > 150:
            return x[np.linspace(0, len(x)-1, 150).astype(int)]
        return x
    a, b = ds(a), ds(b)
    n, m = len(a), len(b)
    D = np.full((n+1, m+1), np.inf); D[0,0] = 0
    for i in range(1, n+1):
        for j in range(1, m+1):
            D[i,j] = np.linalg.norm(a[i-1]-b[j-1]) + min(D[i-1,j], D[i,j-1], D[i-1,j-1])
    return float(D[n,m]) / (n+m)

# ============================================================================
# METİN BENZERLİĞİ (karakter bazlı)
# ============================================================================

def text_similarity(a: str, b: str) -> float:
    """Basit karakter örtüşme oranı (0-1)"""
    a = a.strip().replace(' ', '')
    b = b.strip().replace(' ', '')
    if not a or not b: return 0.0
    # Ortak karakter sayısı / max uzunluk
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()

# ============================================================================
# SKORLAMA
# ============================================================================

def get_level(s):
    return 'mükemmel' if s >= 80 else ('iyi' if s >= 60 else 'geliştirilmeli')

def dur_to_score(ratio):
    """Süre oranını skora çevir — sert eğri"""
    if   ratio >= 0.80: return 100.0
    elif ratio >= 0.65: return 70 + (ratio-0.65)/0.15*30
    elif ratio >= 0.45: return 30 + (ratio-0.45)/0.20*40
    else:               return max(0, ratio * 67)

def analyze(user_path, ref_path, ayet_no: int = None):
    uy, sr = load_audio(user_path)
    ry, _  = load_audio(ref_path)

    u_dur = len(uy)/sr*1000
    r_dur = len(ry)/sr*1000
    ratio = u_dur/r_dur if r_dur > 0 else 1.0

    # Süre ceza çarpanı — kısa okuma tüm skorları etkiler
    # 0.75 altında ceza başlar (daha önce 0.80 idi)
    dur_penalty = min(1.0, ratio / 0.75)

    # --- SÜRE / MED ---
    dur_score = dur_to_score(ratio)
    ue = extract_energy(uy, sr)
    re = extract_energy(ry, sr)
    en_d = dtw_distance(ue, re)
    en_score = max(0, min(100, 100 - en_d*300))
    med_score = dur_score*0.85 + en_score*0.15

    # --- MFCC / HARF (süre cezası uygulanır) ---
    um = extract_mfcc(uy, sr)
    rm = extract_mfcc(ry, sr)
    std = np.std(np.vstack([um, rm]), axis=0) + 1e-8
    mfcc_d = dtw_distance(um/std, rm/std)
    harf_score_raw = max(0, min(100, 100 - mfcc_d*18))  # 22→18, hoparlör kaybına tolerans
    harf_score = harf_score_raw * dur_penalty  # kısa okuyunca harf skoru da düşer

    # --- PITCH / TELAFFUZ (süre cezası uygulanır) ---
    up = extract_pitch(uy, sr); rp = extract_pitch(ry, sr)
    up = up[up>0]; rp = rp[rp>0]
    pitch_d = -1.0
    if len(up)>5 and len(rp)>5:
        up_n = (up-np.mean(up))/(np.std(up)+1e-8)
        rp_n = (rp-np.mean(rp))/(np.std(rp)+1e-8)
        pitch_d = dtw_distance(up_n, rp_n)
        tel_score_raw = max(0, min(100, 100 - pitch_d*60))  # 80→60, hoparlör kaybına tolerans
    else:
        tel_score_raw = 50.0
    tel_score = tel_score_raw * dur_penalty

    # --- STT / DİKTE (Groq Whisper API) ---
    stt_score = None
    transcribed = None
    stt_note = None
    stt_error = None
    try:
        if GROQ_API_KEY:
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            with open(user_path, 'rb') as f:
                resp = client.audio.transcriptions.create(
                    file=("audio.wav", f),
                    model="whisper-large-v3-turbo",
                    language="ar",
                    response_format="text"
                )
            transcribed = str(resp).strip()
            if ayet_no and ayet_no in FATIHA_TEXTS:
                expected = FATIHA_TEXTS[ayet_no]
                sim = text_similarity(transcribed, expected)
                stt_score = sim * 100
                if sim < 0.4:
                    stt_note = '🔤 Metin: Okunan kelimeler referanstan çok farklı'
                elif sim < 0.7:
                    stt_note = '🔤 Metin: Bazı kelimeler eksik veya yanlış'
                else:
                    stt_note = '✅ Metin: Doğru okundu'
    except Exception as e:
        import traceback
        stt_error = traceback.format_exc()

    # --- TOPLAM ---
    if stt_score is not None:
        # STT varsa: telaffuz=%15, med=%40, harf=%25, stt=%20
        total = int(tel_score*0.15 + med_score*0.40 + harf_score*0.25 + stt_score*0.20)
    else:
        total = int(tel_score*0.20 + med_score*0.50 + harf_score*0.30)

    # --- NOTLAR ---
    notes = []
    if   tel_score < 55: notes.append('💬 Telaffuz: Ses tonu referanstan çok farklı')
    elif tel_score < 75: notes.append('💬 Telaffuz: Biraz daha geliştirilebilir')
    else:                notes.append('✅ Telaffuz: Çok iyi!')

    if   ratio < 0.45: notes.append(f'📏 Med: Çok kısa okudun — referansın yalnızca %{int(ratio*100)}\'i kadar')
    elif ratio < 0.65: notes.append(f'📏 Med: Kısa okudun (%{int(ratio*100)}) — uzatmalara dikkat et')
    elif ratio < 0.80: notes.append(f'📏 Med: Biraz kısa (%{int(ratio*100)}) — med harflerini uzat')
    elif ratio > 1.50: notes.append(f'📏 Med: Çok uzun okudun (%{int(ratio*100)})')
    else:              notes.append('✅ Med: Süre mükemmel!')

    if   harf_score < 45: notes.append('🗣️ Harf: Harflerin çıkış noktaları referanstan belirgin farklı')
    elif harf_score < 70: notes.append('🗣️ Harf: Artikülasyon geliştirilebilir')
    else:                 notes.append('✅ Harf: Mükemmel!')

    if stt_note:
        notes.append(stt_note)

    return {
        'totalScore': total,
        'telaffuz': {'score': int(tel_score),  'level': get_level(tel_score)},
        'med':      {'score': int(med_score),  'level': get_level(med_score)},
        'harf':     {'score': int(harf_score), 'level': get_level(harf_score)},
        'notes': notes,
        'transcribed': transcribed,
        'stt_error': stt_error,
        'debug': {
            'user_dur_ms': int(u_dur), 'ref_dur_ms': int(r_dur),
            'dur_ratio': round(ratio,2), 'dur_score': round(dur_score,1),
            'dur_penalty': round(dur_penalty,2),
            'mfcc_dtw': round(mfcc_d,4), 'harf_score': round(harf_score,1),
            'pitch_dtw': round(pitch_d,4), 'tel_score': round(tel_score,1),
            'energy_dtw': round(float(en_d),4), 'med_score': round(med_score,1),
            'stt_score': round(stt_score,1) if stt_score is not None else None,
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

        ayet_no = request.form.get('ayet_no', type=int)

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as u:
            request.files['user_audio'].save(u.name); up = u.name
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as r:
            request.files['reference_audio'].save(r.name); rp = r.name

        try:
            result = analyze(up, rp, ayet_no)
            result['success'] = True
            return jsonify(result), 200
        finally:
            os.unlink(up); os.unlink(rp)

    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'groq_configured': bool(GROQ_API_KEY),
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
