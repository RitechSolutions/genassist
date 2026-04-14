import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import '../models/chat_config.dart';

enum VoiceInputState { idle, listening, processing }

class VoiceInputButton extends StatefulWidget {
  final void Function(String text) onResult;
  final GenAgentChatTheme? theme;
  final bool enabled;

  /// When true, uses the same circular 36×36 trailing style as [ChatInputBar]'s send control
  /// (filled background + 18px icon).
  final bool circleActionStyle;

  const VoiceInputButton({
    super.key,
    required this.onResult,
    this.theme,
    this.enabled = true,
    this.circleActionStyle = false,
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
      try {
        await _speech.stop();
      } catch (_) {
        // Avoid tearing down the widget tree if the engine is in a bad state.
      }
      if (!mounted) return;
      setState(() => _state = VoiceInputState.idle);
      _pulseController.stop();
      _pulseController.reset();
    } else {
      setState(() => _state = VoiceInputState.listening);
      _pulseController.repeat(reverse: true);
      try {
        await _speech.listen(
          onResult: (result) {
            if (!mounted) return;
            if (result.finalResult) {
              widget.onResult(result.recognizedWords);
              setState(() => _state = VoiceInputState.idle);
              _pulseController.stop();
              _pulseController.reset();
            }
          },
          listenFor: const Duration(seconds: 30),
          pauseFor: const Duration(seconds: 3),
          listenOptions: stt.SpeechListenOptions(
            cancelOnError: true,
            partialResults: true,
            listenMode: stt.ListenMode.dictation,
          ),
        );
      } catch (_) {
        if (!mounted) return;
        setState(() => _state = VoiceInputState.idle);
        _pulseController.stop();
        _pulseController.reset();
      }
    }
  }

  @override
  void dispose() {
    try {
      _speech.stop();
    } catch (_) {}
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final primaryColor = widget.theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor;
    final isListening = _state == VoiceInputState.listening;

    if (widget.circleActionStyle) {
      const bgDisabled = Color(0xFFE7E7EC);
      const iconDisabled = Color(0xFF9F9FA8);
      return AnimatedBuilder(
        animation: _pulseAnimation,
        builder: (context, child) {
          final scale = isListening ? _pulseAnimation.value : 1.0;
          final canTap = widget.enabled && _isAvailable;
          final Color bg;
          final Color iconColor;
          if (!widget.enabled) {
            bg = bgDisabled;
            iconColor = iconDisabled;
          } else if (!_isAvailable) {
            bg = bgDisabled;
            iconColor = iconDisabled;
          } else if (isListening) {
            bg = Colors.red;
            iconColor = Colors.white;
          } else {
            bg = primaryColor;
            iconColor = Colors.white;
          }
          return Transform.scale(
            scale: scale,
            child: Tooltip(
              message:
                  !_isAvailable ? 'Voice input unavailable' : (isListening ? 'Stop recording' : 'Voice input'),
              child: InkWell(
                onTap: canTap ? _toggleListening : null,
                borderRadius: BorderRadius.circular(20),
                child: Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: bg,
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: Icon(
                    isListening ? Icons.mic : Icons.mic_none,
                    size: 18,
                    color: iconColor,
                  ),
                ),
              ),
            ),
          );
        },
      );
    }

    if (!_isAvailable) return const SizedBox.shrink();

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
