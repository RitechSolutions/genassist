import 'dart:async';
import 'package:flutter/material.dart';
import '../models/chat_config.dart';

class TypingIndicator extends StatefulWidget {
  final GenAgentChatTheme? theme;
  final List<String> thinkingPhrases;
  final int thinkingDelayMs;

  const TypingIndicator({
    super.key,
    this.theme,
    this.thinkingPhrases = const ['Thinking...'],
    this.thinkingDelayMs = 3000,
  });

  @override
  State<TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<TypingIndicator>
    with TickerProviderStateMixin {
  late AnimationController _dotController;
  Timer? _phraseTimer;
  int _currentPhraseIndex = 0;

  @override
  void initState() {
    super.initState();
    _dotController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();

    if (widget.thinkingPhrases.length > 1) {
      _phraseTimer = Timer.periodic(
        Duration(milliseconds: widget.thinkingDelayMs),
        (_) {
          if (mounted) {
            setState(() {
              _currentPhraseIndex =
                  (_currentPhraseIndex + 1) % widget.thinkingPhrases.length;
            });
          }
        },
      );
    }
  }

  @override
  void dispose() {
    _dotController.dispose();
    _phraseTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final primaryColor = widget.theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor;
    final phrase = widget.thinkingPhrases.isNotEmpty
        ? widget.thinkingPhrases[_currentPhraseIndex]
        : 'Thinking...';

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: const Color(0xFFF3F4F6),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildBouncingDots(primaryColor),
            const SizedBox(width: 10),
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 300),
              child: Text(
                phrase,
                key: ValueKey<int>(_currentPhraseIndex),
                style: TextStyle(
                  fontSize: 13,
                  color: Colors.grey[600],
                  fontStyle: FontStyle.italic,
                  fontFamily: widget.theme?.fontFamily,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBouncingDots(Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(3, (index) {
        return AnimatedBuilder(
          animation: _dotController,
          builder: (context, child) {
            final delay = index * 0.2;
            final progress =
                ((_dotController.value - delay) % 1.0).clamp(0.0, 1.0);
            final bounce = _bounceCurve(progress);
            return Container(
              margin: EdgeInsets.only(right: index < 2 ? 4 : 0),
              child: Transform.translate(
                offset: Offset(0, -bounce * 6),
                child: Container(
                  width: 7,
                  height: 7,
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.7),
                    shape: BoxShape.circle,
                  ),
                ),
              ),
            );
          },
        );
      }),
    );
  }

  double _bounceCurve(double t) {
    if (t < 0.4) {
      return (t / 0.4);
    } else if (t < 0.8) {
      return 1.0 - ((t - 0.4) / 0.4);
    }
    return 0.0;
  }
}
