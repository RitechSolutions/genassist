import React from 'react';
import { AudioLines, Loader2 } from 'lucide-react';
import type { LiveVoiceStatus } from '../hooks/useLiveVoice';

interface LiveCallControlProps {
  status: LiveVoiceStatus;
  isActive: boolean;
  onStart: () => void;
  onStop: () => void;
  theme?: {
    primaryColor?: string;
  };
  disabled?: boolean;
  labels?: {
    start?: string;
    listening?: string;
    speaking?: string;
    connecting?: string;
    end?: string;
  };
}

const BAR_COUNT = 5;

/**
 * Start/End control for a continuous live voice conversation. Presentational:
 * the live session lifecycle lives in {@link useLiveVoice}, surfaced via props.
 */
export const LiveCallControl: React.FC<LiveCallControlProps> = ({
  status,
  isActive,
  onStart,
  onStop,
  theme,
  disabled = false,
  labels,
}) => {
  const primaryColor = theme?.primaryColor || '#4f46e5';

  if (!isActive && status !== 'connecting') {
    return (
      <button
        type="button"
        onClick={onStart}
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
        }}
        title={labels?.start || 'Start live conversation'}
      >
        <AudioLines size={18} color="#ffffff" />
      </button>
    );
  }

  const connecting = status === 'connecting';
  const speaking = status === 'speaking';
  const statusLabel = connecting
    ? labels?.connecting || 'Connecting…'
    : speaking
    ? labels?.speaking || 'Speaking…'
    : labels?.listening || 'Listening…';

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '0 6px',
        backgroundColor: '#fff',
        borderRadius: 24,
        zIndex: 10,
        overflow: 'hidden',
      }}
    >
      {/* Live status dot */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 6px', flexShrink: 0 }}>
        {connecting ? (
          <Loader2 size={14} color={primaryColor} style={{ animation: 'ga-live-spin 0.9s linear infinite' }} />
        ) : (
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: speaking ? primaryColor : '#10b981',
              animation: 'ga-live-pulse 1.4s ease-in-out infinite',
              flexShrink: 0,
            }}
          />
        )}
        <span style={{ fontSize: 13, fontWeight: 600, color: '#374151', fontFamily: 'inherit' }}>
          {statusLabel}
        </span>
      </div>

      {/* Wave animation while active */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 3, height: '100%' }}>
        {Array.from({ length: BAR_COUNT }).map((_, i) => (
          <div
            key={i}
            style={{
              width: 3,
              borderRadius: 3,
              backgroundColor: speaking ? primaryColor : '#10b981',
              opacity: connecting ? 0.3 : 0.8,
              minHeight: 4,
              maxHeight: 20,
              animation: connecting
                ? 'none'
                : `ga-live-wave ${0.6 + (i % 3) * 0.18}s ease-in-out ${i * 0.08}s infinite alternate`,
            }}
          />
        ))}
      </div>

      {/* End call */}
      <button
        type="button"
        onClick={onStop}
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
        }}
        title={labels?.end || 'End conversation'}
      >
        <AudioLines size={16} color="#fff" />
      </button>

      <style>{`
        @keyframes ga-live-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }
        @keyframes ga-live-spin { to { transform: rotate(360deg); } }
        @keyframes ga-live-wave { 0% { height: 4px; } 100% { height: 18px; } }
      `}</style>
    </div>
  );
};
