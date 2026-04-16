// ============================================================================
// TECVID ANALİZ SONUÇ MODELİ
// ============================================================================

class TecvidAnalysisResult {
  final int totalScore;
  final String telaffuzScore;
  final String medScore;
  final String harfScore;
  final List<String> detailedNotes;
  final String? sttNote;
  final String? transcribed;

  TecvidAnalysisResult({
    required this.totalScore,
    required this.telaffuzScore,
    required this.medScore,
    required this.harfScore,
    required this.detailedNotes,
    this.sttNote,
    this.transcribed,
  });
}
