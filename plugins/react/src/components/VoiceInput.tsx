import React, { useState, useRef, useCallback, useEffect } from 'react';
import { Mic, Square, Send, Trash2 } from 'lucide-react';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { AudioPlayer } from './AudioPlayer';

type VoiceState = 'idle' | 'recording' | 'preview';

interface VoiceInputProps {
  onAudioReady: (blob: Blob, format: string) => void;
  onError: (error: Error) => void;
  theme?: {
    primaryColor?: string;
    backgroundColor?: string;
    fontFamily?: string;
  };
  disabled?: boolean;
}

const BAR_COUNT = 32;
const BAR_HEIGHTS = Array.from({ length: BAR_COUNT }, (_, i) => {
  const center = BAR_COUNT / 2;
  const dist = Math.abs(i - center) / center;
  return 0.3 + 0.7 * (1 - dist * dist);
});

export const VoiceInput: React.FC<VoiceInputProps> = ({
  onAudioReady,
  onError,
  theme,
  disabled = false,
}) => {
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [pendingBlob, setPendingBlob] = useState<Blob | null>(null);
  const [pendingFormat, setPendingFormat] = useState<string>('webm');
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const timerRef = useRef<number | null>(null);

  const handleRecordingDone = useCallback((blob: Blob, format: string) => {
    setPendingBlob(blob);
    setPendingFormat(format);
    const url = URL.createObjectURL(blob);
    setBlobUrl(url);
    setVoiceState('preview');
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  }, []);

  const { isRecording, startRecording, stopRecording, cancelRecording } = useAudioRecorder(handleRecordingDone, onError);

  const handleMicClick = useCallback(async () => {
    if (disabled) return;
    setRecordingTime(0);
    await startRecording();
    setVoiceState('recording');
    timerRef.current = window.setInterval(() => setRecordingTime((t) => t + 1), 1000);
  }, [disabled, startRecording]);

  const handleStop = useCallback(() => {
    stopRecording();
  }, [stopRecording]);

  const handleSend = useCallback(() => {
    if (pendingBlob) {
      onAudioReady(pendingBlob, pendingFormat);
    }
    cleanup();
  }, [pendingBlob, pendingFormat, onAudioReady]);

  const handleDiscard = useCallback(() => {
    cleanup();
  }, []);

  const cleanup = () => {
    if (blobUrl) URL.revokeObjectURL(blobUrl);
    setBlobUrl(null);
    setPendingBlob(null);
    setVoiceState('idle');
    setRecordingTime(0);
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, []);

  const primaryColor = theme?.primaryColor || '#4f46e5';

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  if (voiceState === 'idle') {
    return (
      <button
        type="button"
        onClick={handleMicClick}
        disabled={disabled}
        style={{
          position: 'absolute',
          right: 6,
          top: '50%',
          transform: 'translateY(-50%)',
          backgroundColor: primaryColor,
          color: '#ffffff',
          border: 'none',
          borderRadius: '50%',
          width: 36,
          height: 36,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: disabled ? 'not-allowed' : 'pointer',
          flexShrink: 0,
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12)',
          opacity: disabled ? 0.5 : 1,
          zIndex: 5,
          transition: 'opacity 0.15s ease',
        }}
        title="Start Recording"
      >
        <Mic size={18} color="#ffffff" />
      </button>
    );
  }

  if (voiceState === 'recording') {
    return (
      <div style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        gap: 0,
        padding: '0 6px',
        backgroundColor: '#fff',
        borderRadius: 24,
        zIndex: 10,
        overflow: 'hidden',
      }}>
        {/* Discard */}
        <button
          type="button"
          onClick={() => { cancelRecording(); cleanup(); }}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 6,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#9ca3af',
            borderRadius: '50%',
            flexShrink: 0,
            transition: 'color 0.15s ease',
          }}
          title="Cancel"
          onMouseEnter={e => (e.currentTarget.style.color = '#6b7280')}
          onMouseLeave={e => (e.currentTarget.style.color = '#9ca3af')}
        >
          <Trash2 size={18} />
        </button>

        {/* Red dot + Timer */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '0 8px 0 4px',
          flexShrink: 0,
        }}>
          <div style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            backgroundColor: '#ef4444',
            animation: 'ga-rec-pulse 1.5s ease-in-out infinite',
            flexShrink: 0,
          }} />
          <span style={{
            fontSize: 13,
            fontWeight: 600,
            color: '#374151',
            fontVariantNumeric: 'tabular-nums',
            minWidth: 32,
            fontFamily: 'inherit',
          }}>
            {formatTime(recordingTime)}
          </span>
        </div>

        {/* Wave animation */}
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 2,
          height: '100%',
          padding: '0 4px',
          overflow: 'hidden',
        }}>
          {BAR_HEIGHTS.map((scale, i) => (
            <div
              key={i}
              style={{
                width: 2.5,
                borderRadius: 3,
                backgroundColor: primaryColor,
                opacity: 0.55 + 0.45 * scale,
                animation: `ga-wave ${0.6 + (i % 5) * 0.15}s ease-in-out ${i * 0.04}s infinite alternate`,
                minHeight: 3,
                maxHeight: Math.round(scale * 26),
                flexShrink: 0,
              }}
            />
          ))}
        </div>

        {/* Stop button */}
        <button
          type="button"
          onClick={handleStop}
          style={{
            backgroundColor: '#ef4444',
            color: '#fff',
            border: 'none',
            borderRadius: '50%',
            width: 36,
            height: 36,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            flexShrink: 0,
            boxShadow: '0 1px 4px rgba(239, 68, 68, 0.3)',
            transition: 'box-shadow 0.15s ease',
          }}
          title="Stop Recording"
          onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(239, 68, 68, 0.4)')}
          onMouseLeave={e => (e.currentTarget.style.boxShadow = '0 1px 4px rgba(239, 68, 68, 0.3)')}
        >
          <Square size={12} fill="#fff" />
        </button>

        <style>{`
          @keyframes ga-wave {
            0% { height: 3px; }
            100% { height: var(--ga-wave-h, 22px); }
          }
          @keyframes ga-rec-pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
          }
        `}</style>
      </div>
    );
  }

  return (
    <div style={{
      position: 'absolute',
      inset: 0,
      display: 'flex',
      alignItems: 'center',
      gap: 0,
      padding: '0 6px',
      backgroundColor: '#fff',
      borderRadius: 24,
      zIndex: 10,
      overflow: 'hidden',
    }}>
      {/* Discard */}
      <button
        type="button"
        onClick={handleDiscard}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: 6,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#9ca3af',
          borderRadius: '50%',
          flexShrink: 0,
          transition: 'color 0.15s ease',
        }}
        title="Discard"
        onMouseEnter={e => (e.currentTarget.style.color = '#ef4444')}
        onMouseLeave={e => (e.currentTarget.style.color = '#9ca3af')}
      >
        <Trash2 size={18} />
      </button>

      {/* Audio player */}
      <div style={{
        flex: 1,
        minWidth: 0,
        padding: '0 4px',
      }}>
        {blobUrl && <AudioPlayer blobUrl={blobUrl} primaryColor={primaryColor} compact />}
      </div>

      {/* Send */}
      <button
        type="button"
        onClick={handleSend}
        style={{
          backgroundColor: primaryColor,
          color: '#fff',
          border: 'none',
          borderRadius: '50%',
          width: 36,
          height: 36,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          flexShrink: 0,
          boxShadow: `0 1px 4px ${primaryColor}44`,
          transition: 'box-shadow 0.15s ease',
        }}
        title="Send"
        onMouseEnter={e => (e.currentTarget.style.boxShadow = `0 2px 8px ${primaryColor}55`)}
        onMouseLeave={e => (e.currentTarget.style.boxShadow = `0 1px 4px ${primaryColor}44`)}
      >
        <Send size={16} />
      </button>
    </div>
  );
};
