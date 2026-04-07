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
  /// iOS-style sheet: grabber, light surface, [X] + logo + menu, bottom divider.
  final bool sheetStyle;

  const ChatHeader({
    super.key,
    required this.title,
    this.description,
    this.agentName,
    this.logoUrl,
    this.theme,
    this.noColorAnimation = false,
    this.onClose,
    this.sheetStyle = false,
  });

  static const Color _sheetIconColor = Color(0xFF1C1C1E);
  static const Color _sheetDivider = Color(0xFFE5E5EA);

  @override
  Widget build(BuildContext context) {
    final chatState = context.watch<ChatState>();
    final primaryColor = theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor;
    final translations = defaultTranslations;

    if (sheetStyle) {
      return _buildSheetHeader(
        context,
        chatState,
        translations,
        primaryColor,
      );
    }

    final textColor = Colors.white;
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
            _buildLogo(primaryColor, forSheet: false),
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
                        color: textColor.withValues(alpha: 0.8),
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

  Widget _buildSheetHeader(
    BuildContext context,
    ChatState chatState,
    Translations translations,
    Color primaryColor,
  ) {
    final surface = theme?.backgroundColor ?? Colors.white;

    return Material(
      color: surface,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SafeArea(
            bottom: false,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const SizedBox(height: 12),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  child: Row(
                    children: [
                      if (onClose != null)
                        IconButton(
                          icon: const Icon(Icons.close, color: _sheetIconColor, size: 24),
                          onPressed: onClose,
                          tooltip: 'Close',
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(minWidth: 44, minHeight: 44),
                        )
                      else
                        const SizedBox(width: 8),
                      Expanded(
                        child: Align(
                          alignment: Alignment.centerLeft,
                          child: _buildLogo(primaryColor, forSheet: true),
                        ),
                      ),
                      _buildMenuButton(
                        context,
                        chatState,
                        translations,
                        _sheetIconColor,
                      ),
                    ],
                  ),
                ),
                if (description != null && description!.isNotEmpty) ...[
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
                    child: Text(
                      description!,
                      style: TextStyle(
                        color: _sheetIconColor.withValues(alpha: 0.65),
                        fontSize: 13,
                        fontFamily: theme?.fontFamily,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const Divider(height: 1, thickness: 0.5, color: _sheetDivider),
        ],
      ),
    );
  }

  Widget _buildLogo(Color primaryColor, {required bool forSheet}) {
    final maxH = forSheet ? 36.0 : 40.0;
    final maxW = forSheet ? 200.0 : 40.0;

    if (logoUrl != null && logoUrl!.isNotEmpty) {
      return ConstrainedBox(
        constraints: BoxConstraints(maxHeight: maxH, maxWidth: maxW),
        child: Image.network(
          logoUrl!,
          fit: BoxFit.contain,
          alignment: Alignment.centerLeft,
          errorBuilder: (_, __, ___) => _defaultLogoIcon(primaryColor, forSheet: forSheet),
        ),
      );
    }
    return _defaultLogoIcon(primaryColor, forSheet: forSheet);
  }

  Widget _defaultLogoIcon(Color primaryColor, {required bool forSheet}) {
    final size = forSheet ? 36.0 : 40.0;
    final iconColor = forSheet ? _sheetIconColor : Colors.white;
    final bg = forSheet ? const Color(0xFFF2F2F7) : Colors.white.withValues(alpha: 0.2);

    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(size / 2),
      ),
      child: Icon(
        Icons.smart_toy_outlined,
        color: iconColor,
        size: size * 0.55,
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
                const Icon(Icons.restart_alt, size: 20, color: Color(0xFFB42318)),
                const SizedBox(width: 8),
                Text(
                  getTranslationString(
                    'menu.resetConversation',
                    translations,
                    fallback: 'Reset conversation',
                  ),
                  style: const TextStyle(
                    color: Color(0xFFB42318),
                    fontWeight: FontWeight.w600,
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
        final resetLabel = getTranslationString(
          'buttons.reset',
          translations,
          fallback: 'Reset',
        );
        final cancelLabel = getTranslationString(
          'buttons.cancel',
          translations,
          fallback: 'Cancel',
        );
        return AlertDialog(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
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
            OutlinedButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              style: OutlinedButton.styleFrom(
                side: const BorderSide(color: Color(0xFFD0D5DD)),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              ),
              child: Text(
                cancelLabel,
                style: const TextStyle(
                  color: Color(0xFF344054),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            ElevatedButton.icon(
              onPressed: () {
                Navigator.of(dialogContext).pop(true);
                chatState.resetConversation();
              },
              icon: const Icon(Icons.restart_alt, size: 18),
              label: Text(resetLabel),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFB42318),
                foregroundColor: Colors.white,
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
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
