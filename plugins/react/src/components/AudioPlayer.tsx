import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Play, Pause } from 'lucide-react';

interface AudioPlayerProps {
  audioUrl?: string;
  headers?: Record<string, string>;
  blobUrl?: string;
  primaryColor?: string;
  autoPlay?: boolean;
  compact?: boolean;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export const AudioPlayer: React.FC<AudioPlayerProps> = ({
  audioUrl,
  headers,
  blobUrl,
  primaryColor = '#4f46e5',
  autoPlay = false,
  compact = false,
}) => {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const progressRef = useRef<HTMLDivElement>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);

  const initAudio = useCallback((url: string, ownsUrl: boolean) => {
    const audio = new Audio(url);
    audioRef.current = audio;
    if (ownsUrl) objectUrlRef.current = url;

    audio.addEventListener('loadedmetadata', () => {
      setDuration(audio.duration);
      setLoaded(true);
      setLoading(false);
    });
    audio.addEventListener('timeupdate', () => setCurrentTime(audio.currentTime));
    audio.addEventListener('ended', () => {
      setIsPlaying(false);
      setCurrentTime(0);
    });
    return audio;
  }, []);

  const loadAudio = useCallback(async () => {
    if (loaded || loading) return audioRef.current;

    if (blobUrl) {
      setLoading(true);
      return initAudio(blobUrl, false);
    }

    if (!audioUrl) return null;
    setLoading(true);
    try {
      const res = await fetch(audioUrl, { headers: headers || {} });
      if (!res.ok) throw new Error(`${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      return initAudio(url, true);
    } catch {
      setLoading(false);
      return null;
    }
  }, [audioUrl, headers, blobUrl, loaded, loading, initAudio]);

  useEffect(() => {
    if (autoPlay) {
      loadAudio().then((audio) => {
        if (audio) {
          audio.play().then(() => setIsPlaying(true)).catch(() => {});
        }
      });
    }
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, []);

  const togglePlay = async () => {
    let audio = audioRef.current;
    if (!audio) {
      audio = await loadAudio();
      if (!audio) return;
    }
    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
    } else {
      await audio.play();
      setIsPlaying(true);
    }
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!audioRef.current || !progressRef.current || !duration) return;
    const rect = progressRef.current.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    audioRef.current.currentTime = ratio * duration;
    setCurrentTime(audioRef.current.currentTime);
  };

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: compact ? 8 : 10,
      padding: compact ? '4px 0' : '8px 12px',
      borderRadius: compact ? 0 : 20,
      backgroundColor: compact ? 'transparent' : '#f3f4f6',
      minWidth: compact ? 0 : 200,
      maxWidth: compact ? 'none' : 280,
    }}>
      <button
        type="button"
        onClick={togglePlay}
        disabled={loading}
        style={{
          background: primaryColor,
          border: 'none',
          borderRadius: '50%',
          width: compact ? 28 : 32,
          height: compact ? 28 : 32,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: loading ? 'wait' : 'pointer',
          flexShrink: 0,
          opacity: loading ? 0.6 : 1,
        }}
      >
        {isPlaying
          ? <Pause size={14} color="#fff" />
          : <Play size={14} color="#fff" style={{ marginLeft: 2 }} />
        }
      </button>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div
          ref={progressRef}
          onClick={handleSeek}
          style={{
            height: 4,
            borderRadius: 2,
            backgroundColor: '#d1d5db',
            cursor: 'pointer',
            position: 'relative',
          }}
        >
          <div style={{
            height: '100%',
            borderRadius: 2,
            backgroundColor: primaryColor,
            width: `${progress}%`,
            transition: 'width 0.1s linear',
          }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#6b7280' }}>
          <span>{formatTime(currentTime)}</span>
          <span>{duration > 0 ? formatTime(duration) : '--:--'}</span>
        </div>
      </div>
    </div>
  );
};
