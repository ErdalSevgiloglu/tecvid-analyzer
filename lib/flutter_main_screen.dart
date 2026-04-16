import 'package:flutter/material.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import 'package:http/http.dart' as http;
import 'package:audioplayers/audioplayers.dart';
import 'dart:convert';
import 'tecvid_analyzer.dart';

// ============================================================================
// FATIHA AYETLERİ VERİSİ
// ============================================================================

class AyetData {
  final int number;
  final String arabic;
  final String transliteration;
  final String audioAsset;

  const AyetData({
    required this.number,
    required this.arabic,
    required this.transliteration,
    required this.audioAsset,
  });
}

const List<AyetData> fatihaAyetleri = [
  AyetData(
    number: 1,
    arabic: 'بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ',
    transliteration: 'bismillahirrahmanirrahim',
    audioAsset: 'assets/audios/Fatiha/1.mp3',
  ),
  AyetData(
    number: 2,
    arabic: 'الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ',
    transliteration: 'alhamdu lillahi rabbil alamin',
    audioAsset: 'assets/audios/Fatiha/2.mp3',
  ),
  AyetData(
    number: 3,
    arabic: 'الرَّحْمَٰنِ الرَّحِيمِ',
    transliteration: 'arrahmanirrahim',
    audioAsset: 'assets/audios/Fatiha/3.mp3',
  ),
  AyetData(
    number: 4,
    arabic: 'مَالِكِ يَوْمِ الدِّينِ',
    transliteration: 'maliki yawmiddin',
    audioAsset: 'assets/audios/Fatiha/4.mp3',
  ),
  AyetData(
    number: 5,
    arabic: 'إِيَّاكَ نَعْبُدُ وَإِيَّاكَ نَسْتَعِينُ',
    transliteration: 'iyyaka nabudu wa iyyaka nastain',
    audioAsset: 'assets/audios/Fatiha/5.mp3',
  ),
  AyetData(
    number: 6,
    arabic: 'اهْدِنَا الصِّرَاطَ الْمُسْتَقِيمَ',
    transliteration: 'ihdinas siratal mustaqim',
    audioAsset: 'assets/audios/Fatiha/6.mp3',
  ),
  AyetData(
    number: 7,
    arabic: 'صِرَاطَ الَّذِينَ أَنْعَمْتَ عَلَيْهِمْ غَيْرِ الْمَغْضُوبِ عَلَيْهِمْ وَلَا الضَّالِّينَ',
    transliteration: 'siratal lazina anamta alayhim ghayril maghdubi alayhim wa lad dallin',
    audioAsset: 'assets/audios/Fatiha/7.mp3',
  ),
];

// ============================================================================
// ANA SCREEN
// ============================================================================

class TecvidAnalyzerScreen extends StatefulWidget {
  @override
  State<TecvidAnalyzerScreen> createState() => _TecvidAnalyzerScreenState();
}

class _TecvidAnalyzerScreenState extends State<TecvidAnalyzerScreen> {
  static const String BACKEND_URL = 'https://tecvid-analyzer.onrender.com';

  // Her ayet için kayıt durumu
  final Map<int, bool> _isRecording = {};
  final Map<int, bool> _isAnalyzing = {};
  final Map<int, String?> _recordingPaths = {};
  final Map<int, TecvidAnalysisResult?> _results = {};
  final Map<int, String?> _errors = {};

  final _audioRecorder = AudioRecorder();
  final _audioPlayer = AudioPlayer();
  int? _activeRecordingAyet;
  int? _playingAyet;

  @override
  void dispose() {
    _audioRecorder.dispose();
    _audioPlayer.dispose();
    super.dispose();
  }

  Future<void> _startRecording(int ayetNo) async {
    try {
      final isPermitted = await _audioRecorder.hasPermission();
      if (!isPermitted) {
        setState(() => _errors[ayetNo] = 'Mikrofon izni gerekli');
        return;
      }

      // Başka ayet kaydediliyorsa durdur
      if (_activeRecordingAyet != null && _activeRecordingAyet != ayetNo) {
        await _stopRecording(_activeRecordingAyet!);
      }

      final tempDir = await getTemporaryDirectory();
      final path = '${tempDir.path}/ayet_$ayetNo.wav';

      await _audioRecorder.start(
        RecordConfig(encoder: AudioEncoder.wav, sampleRate: 44100),
        path: path,
      );

      setState(() {
        _isRecording[ayetNo] = true;
        _activeRecordingAyet = ayetNo;
        _errors[ayetNo] = null;
        _results[ayetNo] = null;
      });
    } catch (e) {
      setState(() => _errors[ayetNo] = 'Kayıt başlatılamadı: $e');
    }
  }

  Future<void> _stopRecording(int ayetNo) async {
    try {
      final path = await _audioRecorder.stop();
      setState(() {
        _isRecording[ayetNo] = false;
        _recordingPaths[ayetNo] = path;
        _activeRecordingAyet = null;
      });
    } catch (e) {
      setState(() => _errors[ayetNo] = 'Kayıt durdurulamadı: $e');
    }
  }

  Future<void> _playReference(int ayetNo, String assetPath) async {
    if (_playingAyet == ayetNo) {
      await _audioPlayer.stop();
      setState(() => _playingAyet = null);
      return;
    }
    setState(() => _playingAyet = ayetNo);
    await _audioPlayer.play(AssetSource(assetPath.replaceFirst('assets/', '')));
    _audioPlayer.onPlayerComplete.listen((_) {
      if (mounted) setState(() => _playingAyet = null);
    });
  }

  Future<void> _analyze(int ayetNo, String referenceAsset) async {
    final recordingPath = _recordingPaths[ayetNo];
    if (recordingPath == null) return;

    setState(() {
      _isAnalyzing[ayetNo] = true;
      _errors[ayetNo] = null;
    });

    try {
      var request = http.MultipartRequest('POST', Uri.parse('$BACKEND_URL/analyze'));

      request.files.add(
        await http.MultipartFile.fromPath('user_audio', recordingPath),
      );

      final refBytes = await DefaultAssetBundle.of(context).load(referenceAsset);
      request.files.add(
        http.MultipartFile.fromBytes(
          'reference_audio',
          refBytes.buffer.asUint8List(),
          filename: 'reference.wav',
        ),
      );

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _results[ayetNo] = TecvidAnalysisResult(
            totalScore: data['totalScore'],
            telaffuzScore: data['telaffuz']['level'],
            medScore: data['med']['level'],
            harfScore: data['harf']['level'],
            detailedNotes: List<String>.from(data['notes'] ?? []),
          );
        });
      } else {
        // HTML veya JSON olmayan yanıt gelebilir
        String errMsg = 'Sunucu hatası (${response.statusCode})';
        try {
          final error = jsonDecode(response.body);
          errMsg = error['error'] ?? errMsg;
        } catch (_) {}
        setState(() => _errors[ayetNo] = errMsg);
      }
    } catch (e) {
      setState(() => _errors[ayetNo] = 'İstek hatası: $e');
    } finally {
      setState(() => _isAnalyzing[ayetNo] = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0d1b2e),
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            Expanded(
              child: ListView.separated(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                itemCount: fatihaAyetleri.length,
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemBuilder: (context, index) {
                  final ayet = fatihaAyetleri[index];
                  return _buildAyetCard(ayet);
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
      decoration: BoxDecoration(
        color: const Color(0xFF0d1b2e),
        border: Border(
          bottom: BorderSide(
            color: Colors.white.withOpacity(0.08),
            width: 1,
          ),
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: const Color(0xFF1e3a5f),
            ),
            child: const Icon(Icons.menu_book, color: Color(0xFF60a5fa), size: 20),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Sûre-i Fâtiha',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
              Text(
                '7 Ayet • Tecvid Analizi',
                style: TextStyle(fontSize: 12, color: Colors.white38),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildAyetCard(AyetData ayet) {
    final isRec = _isRecording[ayet.number] ?? false;
    final isAna = _isAnalyzing[ayet.number] ?? false;
    final hasRec = _recordingPaths[ayet.number] != null;
    final result = _results[ayet.number];
    final error = _errors[ayet.number];

    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF132035),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isRec
              ? const Color(0xFFef4444).withOpacity(0.5)
              : Colors.white.withOpacity(0.07),
          width: 1.5,
        ),
      ),
      child: Column(
        children: [
          // ÜST KISIM: Ayet numarası + butonlar
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 12, 0),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: const SizedBox()),
                // Mikrofon butonu
                _circleButton(
                  icon: isRec ? Icons.stop : Icons.mic,
                  color: isRec ? const Color(0xFFef4444) : const Color(0xFF1e3a5f),
                  iconColor: isRec ? Colors.white : const Color(0xFF60a5fa),
                  onTap: isAna
                      ? null
                      : () => isRec
                          ? _stopRecording(ayet.number)
                          : _startRecording(ayet.number),
                ),
                const SizedBox(width: 8),
                // Dinle butonu
                _circleButton(
                  icon: _playingAyet == ayet.number
                      ? Icons.stop_rounded
                      : Icons.volume_up_rounded,
                  color: _playingAyet == ayet.number
                      ? const Color(0xFF1e5f3d)
                      : const Color(0xFF1e3a5f),
                  iconColor: _playingAyet == ayet.number
                      ? const Color(0xFF4ade80)
                      : const Color(0xFF60a5fa),
                  onTap: () => _playReference(ayet.number, ayet.audioAsset),
                ),
                const SizedBox(width: 8),
                // Ayet numarası
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color(0xFF1e3a5f),
                  ),
                  child: Center(
                    child: Text(
                      '${ayet.number}',
                      style: const TextStyle(
                        color: Color(0xFF60a5fa),
                        fontWeight: FontWeight.bold,
                        fontSize: 14,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),

          // ARAPÇA METİN
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Text(
              ayet.arabic,
              textAlign: TextAlign.right,
              textDirection: TextDirection.rtl,
              style: const TextStyle(
                fontSize: 26,
                color: Colors.white,
                height: 1.8,
                fontFamily: 'Scheherazade',
              ),
            ),
          ),

          // TRANSLİTERASYON
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
            child: Text(
              ayet.transliteration,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13,
                color: Colors.white38,
                fontStyle: FontStyle.italic,
              ),
            ),
          ),

          // KAYIT SONRASI ANALİZ BUTONU
          if (hasRec && result == null && !isAna)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
              child: SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: () => _analyze(ayet.number, ayet.audioAsset),
                  icon: const Icon(Icons.analytics, size: 16),
                  label: const Text('Analiz Et'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF4ade80),
                    foregroundColor: Colors.black,
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                ),
              ),
            ),

          // YÜKLENİYOR
          if (isAna)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor: AlwaysStoppedAnimation(Color(0xFF60a5fa)),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text('Analiz ediliyor...', style: TextStyle(color: Colors.white38, fontSize: 13)),
                ],
              ),
            ),

          // SONUÇ
          if (result != null)
            _buildResultRow(result, ayet.number),

          // HATA
          if (error != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
              child: Text(
                error,
                style: const TextStyle(color: Color(0xFFef4444), fontSize: 12),
              ),
            ),
        ],
      ),
    );
  }

  Widget _circleButton({
    required IconData icon,
    required Color color,
    required Color iconColor,
    VoidCallback? onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 36,
        height: 36,
        decoration: BoxDecoration(shape: BoxShape.circle, color: color),
        child: Icon(icon, color: iconColor, size: 18),
      ),
    );
  }

  Widget _buildResultRow(TecvidAnalysisResult result, int ayetNo) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFF0d1b2e),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            // Toplam skor
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _scoreColor(result.totalScore).withOpacity(0.15),
                border: Border.all(color: _scoreColor(result.totalScore), width: 2),
              ),
              child: Center(
                child: Text(
                  '${result.totalScore}%',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.bold,
                    color: _scoreColor(result.totalScore),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            // Detaylar
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _scoreChip('Telaffuz', result.telaffuzScore),
                  const SizedBox(height: 4),
                  _scoreChip('Med', result.medScore),
                  const SizedBox(height: 4),
                  _scoreChip('Harf', result.harfScore),
                ],
              ),
            ),
            // Yeniden dene
            GestureDetector(
              onTap: () => setState(() {
                _results[ayetNo] = null;
                _recordingPaths[ayetNo] = null;
              }),
              child: const Icon(Icons.refresh, color: Colors.white38, size: 20),
            ),
          ],
        ),
      ),
    );
  }

  Widget _scoreChip(String label, String level) {
    final isGood = level == 'iyi' || level == 'mükemmel';
    return Row(
      children: [
        Text(
          '$label: ',
          style: const TextStyle(color: Colors.white38, fontSize: 11),
        ),
        Text(
          level,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.bold,
            color: isGood ? const Color(0xFF4ade80) : const Color(0xFFfbbf24),
          ),
        ),
      ],
    );
  }

  Color _scoreColor(int score) {
    if (score >= 85) return const Color(0xFF4ade80);
    if (score >= 70) return const Color(0xFF60a5fa);
    return const Color(0xFFfbbf24);
  }
}
