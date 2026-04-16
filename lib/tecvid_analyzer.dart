import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

// ============================================================================
// TECVID ANALİZÖRÜ - TecvidAnalyzer
// ============================================================================

class TecvidAnalysisResult {
  final int totalScore;
  final String telaffuzScore;     // iyi, geliştirilmeli, mükemmel
  final String medScore;          // Medenning (uzun ünlü) okunuşu
  final String harfScore;         // Harflerin doğru çıkışı
  final List<String> detailedNotes;
  
  TecvidAnalysisResult({
    required this.totalScore,
    required this.telaffuzScore,
    required this.medScore,
    required this.harfScore,
    required this.detailedNotes,
  });
  
  Map<String, dynamic> toJson() {
    return {
      'totalScore': totalScore,
      'telaffuz': telaffuzScore,
      'med': medScore,
      'harf': harfScore,
      'notes': detailedNotes,
    };
  }
}

// ============================================================================
// TECVID KARŞILAŞTIRMA SERVİSİ
// ============================================================================

class TecvidAnalysisService {
  // Örnek ses özelliklerini depolama (reference audios)
  static const Map<String, Map<String, dynamic>> referenceAudios = {
    'bismillah': {
      'duration': 2500,
      'pitchRange': [130, 180],
      'energyLevels': [0.65, 0.8, 0.75, 0.7],
      'medPositions': [0.4, 0.8],
    },
  };

  /// Kullanıcının ses dosyasını referans ses ile karşılaştırır
  static Future<TecvidAnalysisResult> analyzeTecvid({
    required String userAudioPath,
    required String referenceAudioPath,
    required String surah,
  }) async {
    try {
      // 1. Ses analiz edilir (FFT, pitch, duration vs)
      final userFeatures = await _extractAudioFeatures(userAudioPath);
      final referenceFeatures = await _extractAudioFeatures(referenceAudioPath);

      // 2. Telaffuz karşılaştırması (genel doğruluk)
      final telaffuzScore = _compareTelaffuz(userFeatures, referenceFeatures);

      // 3. Med okunuşu analizi (medenning)
      final medScore = _analyzeMed(userFeatures, referenceFeatures);

      // 4. Harf-sihah analizi (harflerin doğru çıkması)
      final harfScore = _analyzeHuruuf(userFeatures, referenceFeatures);

      // 5. Genel skor hesaplama
      final totalScore = _calculateTotalScore(telaffuzScore, medScore, harfScore);

      return TecvidAnalysisResult(
        totalScore: totalScore,
        telaffuzScore: telaffuzScore['level'] as String,
        medScore: medScore['level'] as String,
        harfScore: harfScore['level'] as String,
        detailedNotes: _generateDetailedFeedback(
          telaffuzScore,
          medScore,
          harfScore,
        ),
      );
    } catch (e) {
      print('Tecvid analiz hatası: $e');
      rethrow;
    }
  }

  /// Ses dosyasından akustik özelliklerini çıkarır
  static Future<Map<String, dynamic>> _extractAudioFeatures(String audioPath) async {
    // Gerçek uygulamada: FFmpeg / Audio Plugin kullanılır
    // Şimdilik mock data
    return {
      'duration': 2500,           // ms
      'pitchValues': [130, 135, 140, 138, 135, 130],  // Hz (6 frame)
      'energyValues': [0.6, 0.75, 0.8, 0.78, 0.72, 0.65],
      'mfccCoefficients': [[], [], []],  // MFC katsayıları
      'formants': {
        // Formant frekansları (vokal analizi için)
        'averageF1': 350,  // Hz
        'averageF2': 1200, // Hz
        'averageF3': 2500, // Hz
      },
      'zerocrossingRate': 0.15,  // Titreşim hızı
      'spectralCentroid': 1800,  // Hz
    };
  }

  /// Genel telaffuz kalitesi (pitch, tempo, clarity)
  static Map<String, dynamic> _compareTelaffuz(
    Map<String, dynamic> user,
    Map<String, dynamic> reference,
  ) {
    final userPitchAvg = (user['pitchValues'] as List).cast<double>().reduce((a, b) => a + b) / 
                         (user['pitchValues'] as List).length;
    final refPitchAvg = (reference['pitchValues'] as List).cast<double>().reduce((a, b) => a + b) / 
                        (reference['pitchValues'] as List).length;

    final pitchDifference = (userPitchAvg - refPitchAvg).abs() / refPitchAvg;
    
    // Enerji (clarity) karşılaştırması
    final userEnergyAvg = (user['energyValues'] as List).cast<double>().reduce((a, b) => a + b) / 
                          (user['energyValues'] as List).length;
    final refEnergyAvg = (reference['energyValues'] as List).cast<double>().reduce((a, b) => a + b) / 
                         (reference['energyValues'] as List).length;

    final energyDifference = (userEnergyAvg - refEnergyAvg).abs() / refEnergyAvg;

    // Kombinasyon skorunun hesaplanması
    double score = 100.0;
    score -= pitchDifference * 20;  // Pitch farkı 0-20 puan düşür
    score -= energyDifference * 15; // Enerji farkı 0-15 puan düşür
    score = score.clamp(0, 100);

    String level = 'geliştirilmeli';
    if (score > 85) level = 'mükemmel';
    else if (score > 70) level = 'iyi';

    return {
      'score': score.toInt(),
      'level': level,
      'pitchAccuracy': (100 - (pitchDifference * 100)).clamp(0, 100).toInt(),
      'clarity': (userEnergyAvg * 100).toInt(),
    };
  }

  /// Med okunuşu analizi (medenning uzun ünlüleri)
  static Map<String, dynamic> _analyzeMed(
    Map<String, dynamic> user,
    Map<String, dynamic> reference,
  ) {
    // Med harfleri: ا ي و (Alif, Ya, Vav)
    // Bu harflerin uzunluğu, kontrol edilmelidir

    final userDuration = user['duration'] as int;
    final refDuration = reference['duration'] as int;
    final durationRatio = userDuration / refDuration;

    double score = 100.0;

    // Med harfleri için ideal oran: 1.5-2.5x normal harf süresi
    if (durationRatio < 1.3 || durationRatio > 2.8) {
      score -= 25;  // Çok kısa veya çok uzun
    } else if (durationRatio < 1.5 || durationRatio > 2.5) {
      score -= 10;  // Biraz dışında
    }

    // Formant stabilitesi (vokal kalitesi)
    final userFormantDiff = ((user['formants']['averageF2'] as num) - 
                             (user['formants']['averageF1'] as num)).abs();
    final refFormantDiff = ((reference['formants']['averageF2'] as num) - 
                            (reference['formants']['averageF1'] as num)).abs();

    if ((userFormantDiff - refFormantDiff).abs() > 300) {
      score -= 15;
    }

    score = score.clamp(0, 100);

    String level = 'geliştirilmeli';
    if (score > 85) level = 'mükemmel';
    else if (score > 70) level = 'iyi';

    return {
      'score': score.toInt(),
      'level': level,
      'durationRatio': durationRatio.toStringAsFixed(2),
      'vocalQuality': (score * 0.6).toInt(),
    };
  }

  /// Harflerin doğru çıkışı (harf-sihah)
  static Map<String, dynamic> _analyzeHuruuf(
    Map<String, dynamic> user,
    Map<String, dynamic> reference,
  ) {
    // Harf sihahı: Harflerin doğru noktadan çıkması
    // Spektral benzerlik, sıfır geçiş oranı vb. kullanılır

    final userZCR = user['zerocrossingRate'] as double;
    final refZCR = reference['zerocrossingRate'] as double;
    final zcrDifference = (userZCR - refZCR).abs() / refZCR;

    final userCentroid = user['spectralCentroid'] as int;
    final refCentroid = reference['spectralCentroid'] as int;
    final centroidDifference = (userCentroid - refCentroid).abs() / refCentroid;

    double score = 100.0;
    score -= zcrDifference * 25;      // Titreşim farkı
    score -= centroidDifference * 20; // Spektral fark
    score = score.clamp(0, 100);

    String level = 'geliştirilmeli';
    if (score > 85) level = 'mükemmel';
    else if (score > 70) level = 'iyi';

    return {
      'score': score.toInt(),
      'level': level,
      'articulation': (score * 0.8).toInt(),
      'spectralMatch': ((100 - (centroidDifference * 100)).clamp(0, 100)).toInt(),
    };
  }

  /// Toplam skor hesaplama
  static int _calculateTotalScore(
    Map<String, dynamic> telaffuz,
    Map<String, dynamic> med,
    Map<String, dynamic> harf,
  ) {
    // Ağırlıklandırılmış ortalama
    final weighted = (
      (telaffuz['score'] as int) * 0.4 +  // %40
      (med['score'] as int) * 0.35 +      // %35
      (harf['score'] as int) * 0.25       // %25
    );
    return weighted.toInt();
  }

  /// Detaylı geri bildirim üretme
  static List<String> _generateDetailedFeedback(
    Map<String, dynamic> telaffuz,
    Map<String, dynamic> med,
    Map<String, dynamic> harf,
  ) {
    final notes = <String>[];

    final telScore = telaffuz['score'] as int;
    if (telScore < 70) {
      notes.add('💬 Telaffuz: Pitch ve hız ayarını gözden geçir');
    } else if (telScore < 85) {
      notes.add('💬 Telaffuz: Clarity biraz daha artırılabilir');
    } else {
      notes.add('✅ Telaffuz: Çok iyi!');
    }

    final medScore = med['score'] as int;
    if (medScore < 70) {
      notes.add('📏 Med: Med harfleri (ا/ي/و) daha uzun okumaya özen göster');
    } else if (medScore < 85) {
      notes.add('📏 Med: Med harfleri biraz daha uzatılabilir');
    } else {
      notes.add('✅ Med: Mükemmel!');
    }

    final harfScore = harf['score'] as int;
    if (harfScore < 70) {
      notes.add('🗣️ Harf: Harfleri daha net ve doğru noktadan çıkart');
    } else if (harfScore < 85) {
      notes.add('🗣️ Harf: Artikülasyon biraz daha keskinleştirilebilir');
    } else {
      notes.add('✅ Harf: Mükemmel!');
    }

    return notes;
  }
}

// ============================================================================
// UI KOMPONENTİ - SONUÇ GÖSTER
// ============================================================================

class TecvidResultWidget extends StatelessWidget {
  final TecvidAnalysisResult result;

  const TecvidResultWidget({
    Key? key,
    required this.result,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            const Color(0xFF1a2d4d),
            const Color(0xFF0f1f35),
          ],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: _scoreColor(result.totalScore).withOpacity(0.5),
          width: 2,
        ),
      ),
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          // TOPLAM SKOR
          _buildTotalScore(),
          const SizedBox(height: 24),

          // DETAY KARTLARI
          _buildDetailCards(),
          const SizedBox(height: 20),

          // NOT LİSTESİ
          _buildNotesList(),
        ],
      ),
    );
  }

  Widget _buildTotalScore() {
    return Column(
      children: [
        Text(
          'Toplam Skor',
          style: TextStyle(
            fontSize: 16,
            color: Colors.white70,
            fontWeight: FontWeight.w500,
          ),
        ),
        const SizedBox(height: 12),
        Container(
          width: 120,
          height: 120,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: LinearGradient(
              colors: [
                _scoreColor(result.totalScore),
                _scoreColor(result.totalScore).withOpacity(0.6),
              ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            boxShadow: [
              BoxShadow(
                color: _scoreColor(result.totalScore).withOpacity(0.4),
                blurRadius: 20,
                spreadRadius: 4,
              ),
            ],
          ),
          child: Center(
            child: Text(
              '${result.totalScore}%',
              style: const TextStyle(
                fontSize: 48,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildDetailCards() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceAround,
      children: [
        _buildDetailCard(
          title: 'Telaffuz',
          level: result.telaffuzScore,
          icon: '💬',
        ),
        _buildDetailCard(
          title: 'Med',
          level: result.medScore,
          icon: '📏',
        ),
        _buildDetailCard(
          title: 'Harf',
          level: result.harfScore,
          icon: '🗣️',
        ),
      ],
    );
  }

  Widget _buildDetailCard({
    required String title,
    required String level,
    required String icon,
  }) {
    final isGood = level == 'iyi' || level == 'mükemmel';
    return Container(
      width: 100,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isGood
            ? const Color(0xFF1e5f3d).withOpacity(0.3)
            : const Color(0xFF5f3d1e).withOpacity(0.3),
        border: Border.all(
          color: isGood
              ? const Color(0xFF4ade80).withOpacity(0.5)
              : const Color(0xFFfbbf24).withOpacity(0.5),
          width: 1,
        ),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          Text(
            icon,
            style: const TextStyle(fontSize: 24),
          ),
          const SizedBox(height: 8),
          Text(
            title,
            style: const TextStyle(
              fontSize: 12,
              color: Colors.white70,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            level,
            style: TextStyle(
              fontSize: 11,
              color: isGood ? const Color(0xFF4ade80) : const Color(0xFFfbbf24),
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNotesList() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Geri Bildirim',
          style: TextStyle(
            fontSize: 14,
            color: Colors.white,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 12),
        ...result.detailedNotes.map(
          (note) => Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              note,
              style: const TextStyle(
                fontSize: 13,
                color: Colors.white70,
              ),
            ),
          ),
        ),
      ],
    );
  }

  Color _scoreColor(int score) {
    if (score >= 85) return const Color(0xFF4ade80);  // Yeşil
    if (score >= 70) return const Color(0xFF60a5fa);  // Mavi
    return const Color(0xFFfbbf24);                    // Sarı
  }
}
