import 'dart:convert';
import 'package:flutter/services.dart';

class Translations {
  final Map<String, dynamic> _data;
  Translations(this._data);
  Map<String, dynamic> get data => _data;
}

// Default translations (hardcoded English as fallback)
final Map<String, dynamic> _defaultEnglishData = {
  'header': {'subtitle': 'Support'},
  'menu': {
    'title': 'Menu',
    'resetConversation': 'Reset conversation',
    'fullscreen': 'Fullscreen',
    'language': 'Language',
  },
  'buttons': {
    'startConversation': 'Start Conversation',
    'cancel': 'Cancel',
    'reset': 'Reset',
    'save': 'Save',
    'saveChanges': 'Save Changes',
    'add': 'Add',
  },
  'input': {'placeholder': 'Ask a question'},
  'fileUpload': {'fileTypeNotSupported': 'This file type is not supported.'},
  'labels': {'agent': 'Agent', 'you': 'You'},
  'dialog': {
    'resetConversation': {
      'title': 'Reset Conversation',
      'message':
          'This will clear the current conversation history and start a new conversation. Are you sure?',
    },
  },
  'feedback': {'thumbsUp': 'Thumbs up', 'thumbsDown': 'Thumbs down'},
  'thinking': {
    'messages': [
      'Thinking…',
      'Analyzing your question…',
      'Searching knowledge…',
      'Pulling relevant info…',
      'Drafting the answer…',
      'Double-checking details…',
      'Tying it together…',
      'Almost there…',
    ],
  },
  'time': {'justNow': 'Just now', 'today': 'Today', 'yesterday': 'Yesterday'},
  'settings': {'defaultDescription': 'Support'},
  'metadata': {
    'addParameter': 'Add Parameter',
    'editParameter': 'Edit Parameter',
    'defineKeyValue':
        'Define key/value parameters sent as chat metadata.',
  },
};

Translations get defaultTranslations => Translations(_defaultEnglishData);

/// Get translation value by dot-separated key path (e.g. 'header.subtitle')
dynamic getTranslation(String key, Translations translations,
    {String? fallback}) {
  final keys = key.split('.');
  dynamic value = translations.data;
  for (final k in keys) {
    if (value is Map<String, dynamic> && value.containsKey(k)) {
      value = value[k];
    } else {
      return fallback ?? key;
    }
  }
  return value;
}

String getTranslationString(String key, Translations translations,
    {String? fallback}) {
  final value = getTranslation(key, translations);
  if (value is String) return value;
  return fallback ?? key;
}

List<String> getTranslationArray(String key, Translations translations,
    {List<String>? fallback}) {
  final value = getTranslation(key, translations);
  if (value is List) return value.cast<String>();
  return fallback ?? [];
}

/// Resolve language: prop > platform locale > 'en'
String resolveLanguage(String? languageProp) {
  if (languageProp != null && languageProp.isNotEmpty) {
    return languageProp.toLowerCase();
  }
  // Use platform locale - in Flutter we can't easily access this without
  // WidgetsBinding, so default to 'en'
  return 'en';
}

/// Deep merge two maps (source overrides target)
Map<String, dynamic> _deepMerge(
    Map<String, dynamic> target, Map<String, dynamic> source) {
  final output = Map<String, dynamic>.from(target);
  for (final key in source.keys) {
    if (source[key] is Map<String, dynamic> &&
        target[key] is Map<String, dynamic>) {
      output[key] = _deepMerge(
        target[key] as Map<String, dynamic>,
        source[key] as Map<String, dynamic>,
      );
    } else {
      output[key] = source[key];
    }
  }
  return output;
}

Translations mergeTranslations(Map<String, dynamic>? custom,
    {Translations? defaults}) {
  final base = defaults ?? defaultTranslations;
  if (custom == null) return base;
  return Translations(_deepMerge(base.data, custom));
}

/// Load translations for a specific language from bundled JSON asset
Future<Translations> getTranslationsForLanguage(String language) async {
  try {
    final jsonString = await rootBundle
        .loadString('packages/gen_agent_chat/lib/src/l10n/$language.json');
    final data = json.decode(jsonString) as Map<String, dynamic>;
    return Translations(_deepMerge(_defaultEnglishData, data));
  } catch (_) {
    return defaultTranslations;
  }
}
