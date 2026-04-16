import 'package:flutter/material.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import 'package:http/http.dart' as http;
import 'dart:io';
import 'dart:convert';
import 'tecvid_analyzer.dart';

// ============================================================================
// ANA SCREEN - TECVİD ANALYZER
// ============================================================================

class TecvidAnalyzerScreen extends StatefulWidget {
  @override
  State<TecvidAnalyzerScreen> createState() => _TecvidAnalyzerScreenState();
}

class _TecvidAnalyzerScreenState extends State<TecvidAnalyzerScreen> {
  final _audioRecorder = AudioRecorder();
  
  String? _recordingPath;
  bool _isRecording = false;
  bool _isAnalyzing = false;
  
  TecvidAnalysisResult? _result;
  String? _errorMessage;
  
  // Flask backend URL
  static const String BACKEND_URL = 'https://tecvid-backend.onrender.com';
  
  // Referans ses dosyaları (örneğin assets'ten)
  static const String REFERENCE_AUDIO_PATH = 'assets/audios/bismillah_reference.wav';

  @override
  void dispose() {
    _audioRecorder.dispose();
    super.dispose();
  }

  Future<void> _startRecording() async {
    try {
      final isPermitted = await _audioRecorder.hasPermission();
      if (!isPermitted) {
        setState(() => _errorMessage = 'Mikrofon izni gerekli');
        return;
      }

      final tempDir = await getTemporaryDirectory();
      _recordingPath = '${tempDir.path}/user_recording.wav';

      await _audioRecorder.start(
        RecordConfig(
          encoder: AudioEncoder.wav,
          bitRate: 128000,
          sampleRate: 44100,
        ),
        path: _recordingPath!,
      );

      setState(() => _isRecording = true);
    } catch (e) {
      setState(() => _errorMessage = 'Kayıt başlatılamadı: $e');
    }
  }

  Future<void> _stopRecording() async {
    try {
      final path = await _audioRecorder.stop();
      setState(() {
        _isRecording = false;
        _recordingPath = path;
      });
    } catch (e) {
      setState(() => _errorMessage = 'Kayıt durdurulurken hata: $e');
    }
  }

  Future<void> _analyzeWithBackend() async {
    if (_recordingPath == null) {
      setState(() => _errorMessage = 'Önce ses kaydı yapın');
      return;
    }

    setState(() {
      _isAnalyzing = true;
      _errorMessage = null;
    });

    try {
      // Multipart request hazırlama
      var request = http.MultipartRequest('POST', Uri.parse('$BACKEND_URL/analyze'));

      // Kullanıcı sesi ekle
      request.files.add(
        await http.MultipartFile.fromPath('user_audio', _recordingPath!),
      );

      // Referans sesi ekle (assets'ten veya sunucudan)
      // Bu örnekte sunucudan alıyoruz
      final refBytes = await _downloadReferenceAudio();
      request.files.add(
        http.MultipartFile.fromBytes('reference_audio', refBytes, filename: 'reference.wav'),
      );

      // Request gönder
      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        setState(() {
          _result = TecvidAnalysisResult(
            totalScore: data['totalScore'],
            telaffuzScore: data['telaffuz']['level'],
            medScore: data['med']['level'],
            harfScore: data['harf']['level'],
            detailedNotes: List<String>.from(data['notes'] ?? []),
          );
        });
      } else {
        final error = jsonDecode(response.body);
        setState(() => _errorMessage = error['error'] ?? 'Analiz başarısız');
      }
    } catch (e) {
      setState(() => _errorMessage = 'İstek hatası: $e');
    } finally {
      setState(() => _isAnalyzing = false);
    }
  }

  Future<List<int>> _downloadReferenceAudio() async {
    // Sunucudaki referans ses dosyasını indir
    // Veya assets'ten oku
    final assetData = await DefaultAssetBundle.of(context)
        .load(REFERENCE_AUDIO_PATH);
    return assetData.buffer.asUint8List();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0f1f35),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              // BAŞLIK
              _buildHeader(),
              const SizedBox(height: 40),

              // KAYıT KONTROLÜ
              if (_result == null) ...[
                _buildRecordingSection(),
                const SizedBox(height: 30),
              ],

              // SONUÇ
              if (_result != null) ...[
                TecvidResultWidget(result: _result!),
                const SizedBox(height: 20),
                _buildReplayButton(),
              ],

              // HATA MESAJI
              if (_errorMessage != null) ...[
                const SizedBox(height: 20),
                _buildErrorMessage(),
              ],

              // YÜKLENİYOR
              if (_isAnalyzing) ...[
                const SizedBox(height: 20),
                _buildLoadingIndicator(),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Column(
      children: [
        const Text(
          'Tecvid Analizörü',
          style: TextStyle(
            fontSize: 28,
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Kur\'an tilavetinizi analiz edin',
          style: TextStyle(
            fontSize: 14,
            color: Colors.white60,
          ),
        ),
      ],
    );
  }

  Widget _buildRecordingSection() {
    return Column(
      children: [
        // KAYIT DURUMU
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: const Color(0xFF1a2d4d),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: _isRecording
                  ? const Color(0xFFef4444).withOpacity(0.5)
                  : const Color(0xFF60a5fa).withOpacity(0.3),
              width: 2,
            ),
          ),
          child: Column(
            children: [
              if (_isRecording)
                Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color(0xFFef4444).withOpacity(0.1),
                  ),
                  child: Center(
                    child: Container(
                      width: 60,
                      height: 60,
                      decoration: const BoxDecoration(
                        shape: BoxShape.circle,
                        color: Color(0xFFef4444),
                      ),
                      child: const Icon(Icons.fiber_manual_record,
                          color: Colors.white, size: 28),
                    ),
                  ),
                )
              else
                Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: LinearGradient(
                      colors: [
                        const Color(0xFF60a5fa).withOpacity(0.3),
                        const Color(0xFF3b82f6).withOpacity(0.1),
                      ],
                    ),
                  ),
                  child: const Icon(Icons.mic, color: Color(0xFF60a5fa), size: 40),
                ),
              const SizedBox(height: 16),
              Text(
                _isRecording ? 'Kaydediliyor...' : 'Kayıt yapmaya hazır',
                style: TextStyle(
                  fontSize: 16,
                  color: Colors.white70,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),

        // KONTROL BUTONLARI
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ElevatedButton.icon(
              onPressed: _isRecording ? null : _startRecording,
              icon: const Icon(Icons.mic),
              label: const Text('Başla'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF60a5fa),
                foregroundColor: Colors.white,
                disabledBackgroundColor: Colors.grey,
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              ),
            ),
            const SizedBox(width: 16),
            ElevatedButton.icon(
              onPressed: _isRecording ? _stopRecording : null,
              icon: const Icon(Icons.stop),
              label: const Text('Durdur'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFef4444),
                foregroundColor: Colors.white,
                disabledBackgroundColor: Colors.grey,
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              ),
            ),
          ],
        ),
        const SizedBox(height: 24),

        // ANALİZ BUTONU
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: (_recordingPath != null && !_isAnalyzing && !_isRecording)
                ? _analyzeWithBackend
                : null,
            icon: const Icon(Icons.analytics),
            label: const Text('Analiz Et'),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF4ade80),
              foregroundColor: Colors.black,
              disabledBackgroundColor: Colors.grey,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildReplayButton() {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: () {
          setState(() {
            _result = null;
            _recordingPath = null;
            _errorMessage = null;
          });
        },
        icon: const Icon(Icons.refresh),
        label: const Text('Yeniden Dene'),
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF60a5fa),
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
    );
  }

  Widget _buildErrorMessage() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFef4444).withOpacity(0.1),
        border: Border.all(
          color: const Color(0xFFef4444).withOpacity(0.5),
          width: 1,
        ),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: Color(0xFFef4444)),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              _errorMessage!,
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 13,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoadingIndicator() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF1a2d4d),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: const Color(0xFF60a5fa).withOpacity(0.3),
          width: 1,
        ),
      ),
      child: Column(
        children: [
          const CircularProgressIndicator(
            valueColor: AlwaysStoppedAnimation<Color>(Color(0xFF60a5fa)),
          ),
          const SizedBox(height: 16),
          const Text(
            'Ses analiz ediliyor...',
            style: TextStyle(
              color: Colors.white70,
              fontSize: 14,
            ),
          ),
        ],
      ),
    );
  }
}
