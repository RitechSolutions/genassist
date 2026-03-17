/// Format a language code into an Accept-Language header value.
///
/// Maps short language codes (e.g. 'en') to full locale codes (e.g. 'en-US')
/// and builds a weighted preference list.
String formatAcceptLanguage(String langCode) {
  if (langCode.isEmpty) return '';

  final normalized = langCode.toLowerCase().trim();

  const languageMap = {
    'en': 'en-US',
    'es': 'es-ES',
    'fr': 'fr-FR',
    'de': 'de-DE',
    'it': 'it-IT',
    'pt': 'pt-PT',
    'ar': 'ar-SA',
    'sq': 'sq-AL',
  };

  final hasRegion = normalized.contains('-');
  final fullLocale =
      hasRegion ? normalized : (languageMap[normalized] ?? normalized);
  final baseLang = fullLocale.split('-')[0].toLowerCase();

  final parts = <String>[fullLocale, '$baseLang;q=0.9'];
  if (baseLang != 'en') {
    parts.add('en;q=0.8');
  }

  return parts.join(', ');
}
