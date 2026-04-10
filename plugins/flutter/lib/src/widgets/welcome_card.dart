import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'dart:convert';
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
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (imageUrl != null && imageUrl!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: _buildWelcomeImage(imageUrl!),
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
                textAlign: TextAlign.left,
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
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: possibleQueries.map((query) {
                return Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: ElevatedButton(
                    onPressed: () {
                      chatState.sendMessage(query);
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: primaryColor,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 8,
                      ),
                      alignment: Alignment.centerLeft,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      minimumSize: const Size(0, 0),
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      elevation: 0,
                    ),
                    child: Text(
                      query,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        fontFamily: theme?.fontFamily,
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
        ],
      ),
    );
  }

  Widget _buildWelcomeImage(String source) {
    // Support both regular URLs and data URIs returned by fetchWelcomeImage().
    if (source.startsWith('data:image/')) {
      try {
        final commaIdx = source.indexOf(',');
        if (commaIdx > -1 && commaIdx < source.length - 1) {
          final base64Payload = source.substring(commaIdx + 1);
          final bytes = base64Decode(base64Payload);
          return Image.memory(
            bytes,
            height: 120,
            fit: BoxFit.contain,
            alignment: Alignment.centerLeft,
            errorBuilder: (_, __, ___) => const SizedBox.shrink(),
          );
        }
      } catch (_) {
        return const SizedBox.shrink();
      }
    }

    return Image.network(
      source,
      height: 120,
      fit: BoxFit.contain,
      alignment: Alignment.centerLeft,
      errorBuilder: (_, __, ___) => const SizedBox.shrink(),
    );
  }
}
