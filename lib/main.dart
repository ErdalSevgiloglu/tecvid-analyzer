import 'package:flutter/material.dart';
import 'flutter_main_screen.dart';

void main() {
  runApp(const TecvidApp());
}

class TecvidApp extends StatelessWidget {
  const TecvidApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Tecvid Analizörü',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark(),
      home: TecvidAnalyzerScreen(),
    );
  }
}
