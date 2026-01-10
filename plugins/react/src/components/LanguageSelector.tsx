import React from 'react';
import { Globe } from 'lucide-react';
import { Translations } from '../types';
import { getTranslationString } from '../utils/i18n';

export interface LanguageSelectorProps {
  availableLanguages: Array<{ code: string; name: string }>;
  selectedLanguage: string;
  onLanguageChange: (languageCode: string) => void;
  translations: Translations;
  theme?: {
    primaryColor?: string;
    backgroundColor?: string;
    textColor?: string;
    fontFamily?: string;
    fontSize?: string;
  };
}

export const LanguageSelector: React.FC<LanguageSelectorProps> = ({
  availableLanguages,
  selectedLanguage,
  onLanguageChange,
  translations,
  theme,
}) => {
  // Translation helper
  const t = (key: string, fallback?: string): string => {
    return getTranslationString(key, translations, fallback);
  };

  const primaryColor = theme?.primaryColor || '#2962FF';
  const backgroundColor = theme?.backgroundColor || '#ffffff';
  const textColor = theme?.textColor || '#000000';
  const fontFamily = theme?.fontFamily || 'Roboto, Arial, sans-serif';

  const containerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px 20px',
    gap: '16px',
  };

  const titleStyle: React.CSSProperties = {
    fontSize: '14px',
    fontWeight: 600,
    color: textColor,
    margin: 0,
    fontFamily,
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  };

  const gridStyle: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: '8px',
    width: '100%',
    maxWidth: '320px',
  };

  const buttonStyle = (isActive: boolean): React.CSSProperties => ({
    padding: '10px 16px',
    backgroundColor: isActive ? primaryColor : backgroundColor,
    color: isActive ? '#ffffff' : textColor,
    border: isActive ? `1px solid ${primaryColor}` : '1px solid #e5e7eb',
    borderRadius: '8px',
    fontSize: '13px',
    fontFamily,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    fontWeight: isActive ? 600 : 400,
    boxShadow: isActive ? `0 2px 4px rgba(0, 0, 0, 0.1)` : 'none',
  });

  return (
    <div style={containerStyle}>
      <div style={titleStyle}>
        <Globe size={18} color={textColor} />
        {t('menu.language')}
      </div>
      <div style={gridStyle}>
        {availableLanguages.map((lang) => (
          <button
            key={lang.code}
            style={buttonStyle(selectedLanguage === lang.code)}
            onClick={() => onLanguageChange(lang.code)}
          >
            {lang.name}
          </button>
        ))}
      </div>
    </div>
  );
};

