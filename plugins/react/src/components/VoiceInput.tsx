import React from 'react';
import { Mic, Loader2 } from 'lucide-react';
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
}

export const VoiceInput: React.FC<VoiceInputProps> = ({
  onTranscription,
  onError,
  baseUrl,
  apiKey,
  theme
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
    toggleRecording();
  };

  const getButtonContent = () => {
    if (isLoading) {
      return (
        <Loader2 
          size={20} 
          color="#757575" 
          style={{
            animation: 'spin 1s linear infinite',
          }}
        />
      );
    }
    return <Mic size={20} color={isRecording ? '#ff0000' : '#757575'} />;
  };

  const getTitle = () => {
    if (isLoading) return 'Connecting...';
    return isRecording ? 'Stop Recording' : 'Start Recording';
  };

  const buttonStyle: React.CSSProperties = {
    backgroundColor: '#ffffff',
    color: isRecording ? '#ff0000' : '#757575',
    border: 'none',
    borderRadius: '8px',
    width: '48px',
    height: '48px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: isLoading ? 'not-allowed' : 'pointer',
    outline: 'none',
    transition: 'all 0.2s ease',
    flexShrink: 0,
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
    opacity: isLoading ? 0.7 : 1,
  };

  // Keyframe animation for the spinner
  const spinKeyframes = `
    @keyframes spin {
      from {
        transform: rotate(0deg);
      }
      to {
        transform: rotate(360deg);
      }
    }
  `;

  return (
    <>
      <style>{spinKeyframes}</style>
      <button
        type="button"
        style={buttonStyle}
        onClick={handleClick}
        title={getTitle()}
        disabled={isLoading}
      >
        {getButtonContent()}
      </button>
    </>
  );
}; 