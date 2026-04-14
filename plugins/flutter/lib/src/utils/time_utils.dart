import 'i18n.dart';

/// Format a timestamp (in seconds or milliseconds) into a human-readable string.
///
/// Returns "Just now", "Today, HH:mm", "Yesterday, HH:mm",
/// or "MMM d, yyyy, HH:mm" depending on how recent the timestamp is.
String formatTimestamp(
  double timestamp, {
  String? language,
  Translations? translations,
}) {
  try {
    if (timestamp == 0 || timestamp.isNaN) {
      return _justNow(translations);
    }

    // Normalize to milliseconds
    final timestampMs =
        timestamp < 1000000000000 ? (timestamp * 1000).toInt() : timestamp.toInt();
    final date = DateTime.fromMillisecondsSinceEpoch(timestampMs);

    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));
    final dateDay = DateTime(date.year, date.month, date.day);

    final timeStr = _formatTime(date);

    if (dateDay == today) {
      final todayLabel = translations != null
          ? getTranslationString('time.today', translations, fallback: 'Today')
          : 'Today';
      return '$todayLabel, $timeStr';
    } else if (dateDay == yesterday) {
      final yesterdayLabel = translations != null
          ? getTranslationString('time.yesterday', translations,
              fallback: 'Yesterday')
          : 'Yesterday';
      return '$yesterdayLabel, $timeStr';
    } else {
      final dateStr = _formatDate(date);
      return '$dateStr, $timeStr';
    }
  } catch (_) {
    return _justNow(translations);
  }
}

String _justNow(Translations? translations) {
  if (translations != null) {
    return getTranslationString('time.justNow', translations,
        fallback: 'Just now');
  }
  return 'Just now';
}

/// Format time as "h:mm AM/PM"
String _formatTime(DateTime date) {
  final hour = date.hour;
  final minute = date.minute;
  final period = hour >= 12 ? 'PM' : 'AM';
  final displayHour = hour == 0
      ? 12
      : hour > 12
          ? hour - 12
          : hour;
  final minuteStr = minute.toString().padLeft(2, '0');
  return '$displayHour:$minuteStr $period';
}

/// Format date as "MMM d, yyyy"
String _formatDate(DateTime date) {
  const months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ];
  return '${months[date.month - 1]} ${date.day}, ${date.year}';
}
