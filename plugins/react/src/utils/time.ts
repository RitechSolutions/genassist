export interface TimeTranslations {
  justNow: string;
  today: string;
  yesterday: string;
}

export const formatTimestamp = (
  timestamp: number,
  language?: string,
  translations?: TimeTranslations
): string => {
  try {
    if (!timestamp || isNaN(timestamp)) {
      return translations?.justNow || 'Just now';
    }
    const timestampMs = timestamp < 1000000000000 ? timestamp * 1000 : timestamp;
    const date = new Date(timestampMs);
    if (isNaN(date.getTime())) {
      return translations?.justNow || 'Just now';
    }
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    // Use language for locale formatting
    const localeMap: Record<string, string> = {
      'en': 'en-US',
      'es': 'es-ES',
      'fr': 'fr-FR',
      'de': 'de-DE',
      'it': 'it-IT',
      'pt': 'pt-PT',
    };
    const locale = language ? (localeMap[language] || language) : undefined;
    const timeOptions: Intl.DateTimeFormatOptions = { hour: 'numeric', minute: '2-digit', hour12: true };
    const timeStr = date.toLocaleTimeString(locale, timeOptions);
    
    if (date.toDateString() === today.toDateString()) {
      return `${translations?.today || 'Today'}, ${timeStr}`;
    } else if (date.toDateString() === yesterday.toDateString()) {
      return `${translations?.yesterday || 'Yesterday'}, ${timeStr}`;
    } else {
      const dateOptions: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric', year: 'numeric' };
      const dateStr = date.toLocaleDateString(locale, dateOptions);
      return `${dateStr}, ${timeStr}`;
    }
  } catch {
    return translations?.justNow || 'Just now';
  }
};

