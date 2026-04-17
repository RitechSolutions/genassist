import 'package:flutter/material.dart';
import '../models/chat_config.dart';

class ChatBubble extends StatelessWidget {
  final bool isOpen;
  final VoidCallback onToggle;
  final FloatingConfig? config;
  final GenAgentChatTheme? theme;

  const ChatBubble({
    super.key,
    required this.isOpen,
    required this.onToggle,
    this.config,
    this.theme,
  });

  @override
  Widget build(BuildContext context) {
    final primaryColor = theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor;

    final Widget icon;
    if (isOpen) {
      icon = config?.closeButtonIcon ??
          const Icon(Icons.close, color: Colors.white, size: 28);
    } else {
      icon = config?.toggleButtonIcon ??
          const Icon(Icons.chat_bubble_rounded, color: Colors.white, size: 28);
    }

    return SizedBox(
      width: 56,
      height: 56,
      child: FloatingActionButton(
        onPressed: onToggle,
        backgroundColor: primaryColor,
        elevation: 4,
        shape: const CircleBorder(),
        child: AnimatedSwitcher(
          duration: const Duration(milliseconds: 200),
          transitionBuilder: (child, animation) {
            return ScaleTransition(scale: animation, child: child);
          },
          child: KeyedSubtree(
            key: ValueKey<bool>(isOpen),
            child: icon,
          ),
        ),
      ),
    );
  }
}
