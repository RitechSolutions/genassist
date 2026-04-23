import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../state/chat_state.dart';
import '../models/chat_config.dart';

/// A full-page or bottom-sheet language selector widget.
class LanguageSelector extends StatelessWidget {
  final GenAgentChatTheme? theme;

  const LanguageSelector({
    super.key,
    this.theme,
  });

  /// Mapping of language codes to display names.
  static const Map<String, String> _languageNames = {
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'ar': 'Arabic',
    'sq': 'Albanian',
    'zh': 'Chinese',
    'ja': 'Japanese',
    'ko': 'Korean',
    'nl': 'Dutch',
    'ru': 'Russian',
    'tr': 'Turkish',
    'pl': 'Polish',
    'sv': 'Swedish',
    'da': 'Danish',
    'fi': 'Finnish',
    'no': 'Norwegian',
    'cs': 'Czech',
    'ro': 'Romanian',
    'hu': 'Hungarian',
    'el': 'Greek',
    'he': 'Hebrew',
    'th': 'Thai',
    'vi': 'Vietnamese',
    'uk': 'Ukrainian',
    'bg': 'Bulgarian',
    'hr': 'Croatian',
    'sk': 'Slovak',
    'sl': 'Slovenian',
  };

  static String getLanguageName(String code) {
    return _languageNames[code.toLowerCase()] ?? code.toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    final chatState = context.watch<ChatState>();
    final languages = chatState.availableLanguages ?? [];
    final currentLanguage = chatState.currentLanguage;
    final primaryColor = theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor;

    if (languages.isEmpty) {
      return const Center(
        child: Text('No languages available'),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            'Select Language',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              fontFamily: theme?.fontFamily,
              color: theme?.textColor ?? Colors.black87,
            ),
          ),
        ),
        const Divider(height: 1),
        Flexible(
          child: ListView.builder(
            shrinkWrap: true,
            itemCount: languages.length,
            itemBuilder: (context, index) {
              final lang = languages[index];
              final isSelected = lang == currentLanguage;

              return ListTile(
                title: Text(
                  getLanguageName(lang),
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                    color: isSelected
                        ? primaryColor
                        : (theme?.textColor ?? Colors.black87),
                    fontFamily: theme?.fontFamily,
                  ),
                ),
                subtitle: Text(
                  lang.toUpperCase(),
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[500],
                    fontFamily: theme?.fontFamily,
                  ),
                ),
                trailing: isSelected
                    ? Icon(Icons.check_circle, color: primaryColor)
                    : null,
                onTap: () {
                  chatState.setLanguage(lang);
                  Navigator.of(context).pop();
                },
              );
            },
          ),
        ),
      ],
    );
  }
}
