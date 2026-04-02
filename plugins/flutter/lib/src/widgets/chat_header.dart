import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../state/chat_state.dart';
import '../models/chat_config.dart';
import '../utils/i18n.dart';

class ChatHeader extends StatelessWidget {
  final String title;
  final String? description;
  final String? agentName;
  final String? logoUrl;
  final GenAgentChatTheme? theme;
  final bool noColorAnimation;
  final VoidCallback? onClose;

  const ChatHeader({
    super.key,
    required this.title,
    this.description,
    this.agentName,
    this.logoUrl,
    this.theme,
    this.noColorAnimation = false,
    this.onClose,
  });

  @override
  Widget build(BuildContext context) {
    final chatState = context.watch<ChatState>();
    final primaryColor = theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor;
    final textColor = Colors.white;
    final translations = defaultTranslations;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: primaryColor,
      ),
      child: SafeArea(
        bottom: false,
        child: Row(
          children: [
            if (onClose != null) ...[
              IconButton(
                icon: const Icon(Icons.close, color: Colors.white),
                onPressed: onClose,
                tooltip: 'Close',
              ),
              const SizedBox(width: 4),
            ],
            _buildLogo(primaryColor),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    agentName ?? title,
                    style: TextStyle(
                      color: textColor,
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      fontFamily: theme?.fontFamily,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (description != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      description!,
                      style: TextStyle(
                        color: textColor.withOpacity(0.8),
                        fontSize: 12,
                        fontFamily: theme?.fontFamily,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ],
              ),
            ),
            _buildMenuButton(context, chatState, translations, textColor),
          ],
        ),
      ),
    );
  }

  Widget _buildLogo(Color primaryColor) {
    if (logoUrl != null && logoUrl!.isNotEmpty) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: Image.network(
          logoUrl!,
          width: 40,
          height: 40,
          fit: BoxFit.cover,
          errorBuilder: (_, __, ___) => _defaultLogoIcon(primaryColor),
        ),
      );
    }
    return _defaultLogoIcon(primaryColor);
  }

  Widget _defaultLogoIcon(Color primaryColor) {
    return Container(
      width: 40,
      height: 40,
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.2),
        borderRadius: BorderRadius.circular(20),
      ),
      child: const Icon(
        Icons.smart_toy_outlined,
        color: Colors.white,
        size: 24,
      ),
    );
  }

  Widget _buildMenuButton(
    BuildContext context,
    ChatState chatState,
    Translations translations,
    Color textColor,
  ) {
    return PopupMenuButton<String>(
      icon: Icon(Icons.more_vert, color: textColor),
      onSelected: (value) {
        switch (value) {
          case 'reset':
            _showResetConfirmation(context, chatState, translations);
            break;
          case 'language':
            _showLanguageSelector(context, chatState);
            break;
        }
      },
      itemBuilder: (context) {
        final items = <PopupMenuEntry<String>>[
          PopupMenuItem<String>(
            value: 'reset',
            child: Row(
              children: [
                const Icon(Icons.refresh, size: 20),
                const SizedBox(width: 8),
                Text(
                  getTranslationString(
                    'menu.resetConversation',
                    translations,
                    fallback: 'Reset conversation',
                  ),
                ),
              ],
            ),
          ),
        ];

        final availableLanguages = chatState.availableLanguages;
        if (availableLanguages != null && availableLanguages.length > 1) {
          items.add(
            PopupMenuItem<String>(
              value: 'language',
              child: Row(
                children: [
                  const Icon(Icons.language, size: 20),
                  const SizedBox(width: 8),
                  Text(
                    getTranslationString(
                      'menu.language',
                      translations,
                      fallback: 'Language',
                    ),
                  ),
                ],
              ),
            ),
          );
        }

        return items;
      },
    );
  }

  void _showResetConfirmation(
    BuildContext context,
    ChatState chatState,
    Translations translations,
  ) {
    showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: Text(
            getTranslationString(
              'dialog.resetConversation.title',
              translations,
              fallback: 'Reset Conversation',
            ),
          ),
          content: Text(
            getTranslationString(
              'dialog.resetConversation.message',
              translations,
              fallback:
                  'This will clear the current conversation history and start a new conversation. Are you sure?',
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: Text(
                getTranslationString(
                  'buttons.cancel',
                  translations,
                  fallback: 'Cancel',
                ),
              ),
            ),
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop(true);
                chatState.resetConversation();
              },
              child: Text(
                getTranslationString(
                  'buttons.reset',
                  translations,
                  fallback: 'Reset',
                ),
                style: const TextStyle(color: Colors.red),
              ),
            ),
          ],
        );
      },
    );
  }

  void _showLanguageSelector(BuildContext context, ChatState chatState) {
    showModalBottomSheet(
      context: context,
      builder: (sheetContext) {
        final languages = chatState.availableLanguages ?? [];
        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text(
                  'Select Language',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                ),
              ),
              ...languages.map(
                (lang) => ListTile(
                  title: Text(lang.toUpperCase()),
                  trailing: null,
                  onTap: () {
                    Navigator.of(sheetContext).pop();
                    chatState.setLanguage(lang);
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
