/// Simple text-to-speech service using flutter_tts.
/// A lightweight alternative to the React AudioService which uses WebSocket TTS.

import 'package:flutter_tts/flutter_tts.dart';

class AudioService {
  final FlutterTts _tts = FlutterTts();
  bool _isInitialized = false;

  /// Initialize the TTS engine with default settings.
  Future<void> init() async {
    if (_isInitialized) return;
    await _tts.setLanguage('en-US');
    await _tts.setSpeechRate(0.5);
    await _tts.setVolume(1.0);
    _isInitialized = true;
  }

  /// Speak the given text. Optionally override the language.
  Future<void> speak(String text, {String? language}) async {
    await init();
    if (language != null) {
      await _tts.setLanguage(language);
    }
    await _tts.speak(text);
  }

  /// Stop any ongoing speech.
  Future<void> stop() async {
    await _tts.stop();
  }

  /// Clean up resources.
  void dispose() {
    _tts.stop();
  }
}
