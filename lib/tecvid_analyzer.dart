// ============================================================================
// TECVID ANALİZ SONUÇ MODELİ
// ============================================================================

class MissingWord {
  final String arabic;
  final String pronunciation;
  const MissingWord({required this.arabic, required this.pronunciation});
}

class TecvidAnalysisResult {
  final int totalScore;
  final String telaffuzScore;
  final String medScore;
  final String harfScore;
  final List<String> detailedNotes;
  final String? sttNote;
  final String? transcribed;
  final List<MissingWord> missingWords;

  TecvidAnalysisResult({
    required this.totalScore,
    required this.telaffuzScore,
    required this.medScore,
    required this.harfScore,
    required this.detailedNotes,
    this.sttNote,
    this.transcribed,
    this.missingWords = const [],
  });
}
