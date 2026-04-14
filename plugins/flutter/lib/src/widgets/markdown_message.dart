import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/chat_config.dart';

class MarkdownMessage extends StatelessWidget {
  final String text;
  final GenAgentChatTheme? theme;

  const MarkdownMessage({
    super.key,
    required this.text,
    this.theme,
  });

  @override
  Widget build(BuildContext context) {
    return MarkdownBody(
      data: text,
      selectable: true,
      styleSheet: MarkdownStyleSheet(
        p: TextStyle(
          fontSize: theme?.fontSize ?? 14,
          color: theme?.textColor ?? Colors.black87,
          fontFamily: theme?.fontFamily,
          height: 1.5,
        ),
        a: TextStyle(
          color: theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor,
          decoration: TextDecoration.underline,
          fontFamily: theme?.fontFamily,
        ),
        h1: TextStyle(
          fontSize: 22,
          fontWeight: FontWeight.w700,
          color: theme?.textColor ?? Colors.black87,
          fontFamily: theme?.fontFamily,
        ),
        h2: TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w600,
          color: theme?.textColor ?? Colors.black87,
          fontFamily: theme?.fontFamily,
        ),
        h3: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w600,
          color: theme?.textColor ?? Colors.black87,
          fontFamily: theme?.fontFamily,
        ),
        code: TextStyle(
          fontSize: (theme?.fontSize ?? 14) - 1,
          fontFamily: 'monospace',
          backgroundColor: Colors.grey[100],
          color: Colors.pink[700],
        ),
        codeblockDecoration: BoxDecoration(
          color: Colors.grey[100],
          borderRadius: BorderRadius.circular(8),
        ),
        blockquoteDecoration: BoxDecoration(
          border: Border(
            left: BorderSide(
              color: theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor,
              width: 3,
            ),
          ),
        ),
        listBullet: TextStyle(
          fontSize: theme?.fontSize ?? 14,
          color: theme?.textColor ?? Colors.black87,
          fontFamily: theme?.fontFamily,
        ),
      ),
      onTapLink: (text, href, title) async {
        if (href == null) return;
        final uri = Uri.tryParse(href);
        if (uri != null && await canLaunchUrl(uri)) {
          await launchUrl(uri, mode: LaunchMode.externalApplication);
        }
      },
    );
  }
}
