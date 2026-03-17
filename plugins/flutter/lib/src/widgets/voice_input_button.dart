import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import '../models/chat_config.dart';

enum VoiceInputState { idle, listening, processing }

class VoiceInputButton extends StatefulWidget {
  final void Function(String text) onResult;
  final GenAgentChatTheme? theme;
  final bool enabled;

  const VoiceInputButton({
    super.key,
    required this.onResult,
    this.theme,
    this.enabled = true,
  });

  @override
  State<VoiceInputButton> createState() => _VoiceInputButtonState();
}

class _VoiceInputButtonState extends State<VoiceInputButton>
    with SingleTickerProviderStateMixin {
  final stt.SpeechToText _speech = stt.SpeechToText();
  VoiceInputState _state = VoiceInputState.idle;
  bool _isAvailable = false;
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    );
    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.3).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
    _initSpeech();
  }

  Future<void> _initSpeech() async {
    try {
      _isAvailable = await _speech.initialize(
        onStatus: _handleStatus,
        onError: _handleError,
      );
    } catch (_) {
      _isAvailable = false;
    }
    if (mounted) setState(() {});
  }

  void _handleStatus(String status) {
    if (!mounted) return;
    if (status == 'done' || status == 'notListening') {
      setState(() => _state = VoiceInputState.idle);
      _pulseController.stop();
      _pulseController.reset();
    }
  }

  void _handleError(dynamic error) {
    if (!mounted) return;
    setState(() => _state = VoiceInputState.idle);
    _pulseController.stop();
    _pulseController.reset();
  }

  Future<void> _toggleListening() async {
    if (!_isAvailable || !widget.enabled) return;

    if (_state == VoiceInputState.listening) {
      await _speech.stop();
      setState(() => _state = VoiceInputState.idle);
      _pulseController.stop();
      _pulseController.reset();
    } else {
      setState(() => _state = VoiceInputState.listening);
      _pulseController.repeat(reverse: true);
      await _speech.listen(
        onResult: (result) {
          if (result.finalResult) {
            widget.onResult(result.recognizedWords);
            setState(() => _state = VoiceInputState.idle);
            _pulseController.stop();
            _pulseController.reset();
          }
        },
        listenFor: const Duration(seconds: 30),
        pauseFor: const Duration(seconds: 3),
        cancelOnError: true,
      );
    }
  }

  @override
  void dispose() {
    _speech.stop();
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_isAvailable) return const SizedBox.shrink();

    final primaryColor = widget.theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor;
    final isListening = _state == VoiceInputState.listening;

    return AnimatedBuilder(
      animation: _pulseAnimation,
      builder: (context, child) {
        return Transform.scale(
          scale: isListening ? _pulseAnimation.value : 1.0,
          child: IconButton(
            onPressed: widget.enabled ? _toggleListening : null,
            icon: Icon(
              isListening ? Icons.mic : Icons.mic_none,
              color: isListening
                  ? Colors.red
                  : widget.enabled
                      ? primaryColor
                      : Colors.grey[400],
            ),
            tooltip: isListening ? 'Stop recording' : 'Voice input',
          ),
        );
      },
    );
  }
}
