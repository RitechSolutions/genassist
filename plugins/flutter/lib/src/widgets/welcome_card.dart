import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../state/chat_state.dart';
import '../models/chat_config.dart';
import 'markdown_message.dart';

class WelcomeCard extends StatelessWidget {
  final String? title;
  final String? message;
  final String? imageUrl;
  final List<String> possibleQueries;
  final GenAgentChatTheme? theme;
  final String? language;

  const WelcomeCard({
    super.key,
    this.title,
    this.message,
    this.imageUrl,
    this.possibleQueries = const [],
    this.theme,
    this.language,
  });

  @override
  Widget build(BuildContext context) {
    final chatState = context.read<ChatState>();
    final primaryColor = theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          if (imageUrl != null && imageUrl!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.network(
                  imageUrl!,
                  height: 120,
                  fit: BoxFit.contain,
                  errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                ),
              ),
            ),
          if (title != null && title!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                title!,
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: theme?.textColor ?? Colors.black87,
                  fontFamily: theme?.fontFamily,
                ),
                textAlign: TextAlign.center,
              ),
            ),
          if (message != null && message!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: MarkdownMessage(
                text: message!,
                theme: theme,
              ),
            ),
          if (possibleQueries.isNotEmpty)
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: possibleQueries.map((query) {
                return ActionChip(
                  label: Text(
                    query,
                    style: TextStyle(
                      color: primaryColor,
                      fontSize: 13,
                      fontFamily: theme?.fontFamily,
                    ),
                  ),
                  backgroundColor: primaryColor.withOpacity(0.08),
                  side: BorderSide(color: primaryColor.withOpacity(0.3)),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(20),
                  ),
                  onPressed: () {
                    chatState.sendMessage(query);
                  },
                );
              }).toList(),
            ),
        ],
      ),
    );
  }
}
