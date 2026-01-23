import React from 'react';
import { Mic } from 'lucide-react';
import { Spinner } from './Spinner';
import { useVoiceInput } from '../hooks/useVoiceInput';

interface VoiceInputProps {
  onTranscription: (text: string) => void;
  onError: (error: Error) => void;
  baseUrl: string;
  apiKey: string;
  theme?: {
    primaryColor?: string;
    backgroundColor?: string;
    fontFamily?: string;
  };
  disabled?: boolean;
}

export const VoiceInput: React.FC<VoiceInputProps> = ({
  onTranscription,
  onError,
  baseUrl,
  apiKey,
  theme,
  disabled = false
}) => {
  const { isRecording, isLoading, toggleRecording } = useVoiceInput({
    baseUrl,
    apiKey,
    onTranscription,
    onError,
  });

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (disabled) return;
    toggleRecording();
  };

  const getButtonContent = () => {
    if (isLoading) return <Spinner size={18} color="#ffffff" />;
    return <Mic size={18} color="#ffffff" />;
  };

  const getTitle = () => {
    if (isLoading) return 'Connecting...';
    return isRecording ? 'Stop Recording' : 'Start Recording';
  };

  const idleBg = theme?.primaryColor || '#2962FF';
  const activeBg = '#FF3B30'; // red when recording
  const isDisabled = disabled || isLoading;
  const buttonStyle: React.CSSProperties = {
    backgroundColor: isRecording ? activeBg : idleBg,
    color: '#ffffff',
    border: 'none',
    borderRadius: '50%',
    width: '36px',
    height: '36px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: isDisabled ? 'not-allowed' : 'pointer',
    outline: 'none',
    transition: 'all 0.2s ease',
    flexShrink: 0,
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.08)',
    opacity: isDisabled ? 0.6 : 1,
  };

  return (
    <>
      <button
        type="button"
        style={buttonStyle}
        onClick={handleClick}
        title={getTitle()}
        disabled={isDisabled}
      >
        {getButtonContent()}
      </button>
    </>
  );
};
