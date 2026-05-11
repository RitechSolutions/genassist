import React, { useCallback, useEffect, useRef, useState } from 'react';
import { TranscriptEntry } from "@/interfaces/transcript.interface";
import { ClipboardList, Play, Pause, Mic } from "lucide-react";
import { FileText, FileJson, FileImage } from 'lucide-react';
import { getMessageAudioUrl } from '@/services/transcripts';

interface FileData {
  url: string;
  name: string;
  id: string;
  type: string;
}

const getFileIcon = (fileType: string): React.ReactElement => {
  if (fileType.startsWith('image/')) return <FileImage size={24} color="#6D28D9" />;
  if (fileType === 'application/pdf') return <FileText size={24} color="#B91C1C" />;
  if (fileType === 'application/json') return <FileJson size={24} color="#1D4ED8" />;
  return <FileText size={24} color="#4B5563" />;
};


/**
 * FilePreview component
 * @param fileData - The file data
 * @returns The file preview component
 */
function FilePreview({ fileData }: { fileData: FileData }) {
  if (fileData.type && fileData.type.startsWith('image')) {
    return <div className="flex flex-col items-start gap-2 cursor-pointer" onClick={() => window.open(fileData.url, '_blank')}>
      <img className="w-20 h-12 object-cover" src={fileData.url} alt="Image" loading="lazy" />
      <span className="text-xs text-muted-foreground">{fileData.name}</span>
    </div>;
  } else {
    return <div className="flex flex-col items-start gap-2 cursor-pointer" onClick={() => window.open(fileData.url, '_blank')}>
      {getFileIcon(fileData.type)}
      <span className="text-xs text-muted-foreground">{fileData.name}</span>
    </div>;
  }
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function InlineAudioPlayer({
  conversationId,
  messageId,
  isAgent,
}: {
  conversationId: string;
  messageId: string;
  isAgent: boolean;
}) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const progressRef = useRef<HTMLDivElement>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    return () => {
      audioRef.current?.pause();
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
  }, []);

  const loadAudio = useCallback(async () => {
    if (loaded || loading) return audioRef.current;
    setLoading(true);
    try {
      const blobUrl = await getMessageAudioUrl(conversationId, messageId);
      objectUrlRef.current = blobUrl;
      const audio = new Audio(blobUrl);
      audioRef.current = audio;
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
    } catch {
      setLoading(false);
      return null;
    }
  }, [conversationId, messageId, loaded, loading]);

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
  const accent = isAgent ? 'bg-white/80' : 'bg-blue-500';
  const trackBg = isAgent ? 'bg-white/30' : 'bg-gray-300';
  const textColor = isAgent ? 'text-white/70' : 'text-gray-500';
  const btnBg = isAgent
    ? 'bg-white/20 hover:bg-white/30'
    : 'bg-gray-300 hover:bg-gray-400';
  const iconColor = isAgent ? 'text-white' : 'text-gray-700';

  return (
    <div className="flex items-center gap-2 min-w-[180px]">
      <button
        type="button"
        onClick={togglePlay}
        disabled={loading}
        className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${btnBg} transition-colors`}
        style={{ opacity: loading ? 0.6 : 1 }}
      >
        {isPlaying ? (
          <Pause size={12} className={iconColor} />
        ) : (
          <Play size={12} className={`${iconColor} ml-0.5`} />
        )}
      </button>

      <div className="flex-1 flex flex-col gap-1 min-w-0">
        <div
          ref={progressRef}
          onClick={handleSeek}
          className={`h-1 rounded-full cursor-pointer ${trackBg} relative`}
        >
          <div
            className={`h-full rounded-full ${accent} transition-[width] duration-100`}
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className={`flex justify-between text-[10px] ${textColor}`}>
          <span>{formatTime(currentTime)}</span>
          <span>{duration > 0 ? formatTime(duration) : '--:--'}</span>
        </div>
      </div>
    </div>
  );
}

export function ConversationEntryWrapper({
  entry,
  conversationId,
}: {
  entry: TranscriptEntry;
  conversationId?: string;
}) {
  try {
    const messageId = entry.message_id || (entry as any).id;
    if (entry.type === "audio" && messageId && conversationId) {
      const isAgent = ['Agent', 'agent'].includes(entry.speaker);
      return (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1.5 mb-1">
            <Mic size={12} className={isAgent ? 'text-white/70' : 'text-gray-500'} />
            <span className={`text-[11px] ${isAgent ? 'text-white/70' : 'text-gray-500'}`}>
              Voice message
            </span>
          </div>
          <InlineAudioPlayer
            conversationId={conversationId}
            messageId={messageId}
            isAgent={isAgent}
          />
        </div>
      );
    } else if (entry.type === "file") {
      const cleanJson = entry.text && entry.text.replace(/\\/g, '');
      const fileData = cleanJson ? JSON.parse(cleanJson) : null;
      return <FilePreview fileData={fileData as FileData} />;
    } else if (entry.type === "form_request") {
      const cleanJson = entry.text && entry.text.replace(/\\/g, '');
      const formSchema = cleanJson ? JSON.parse(cleanJson) : null;
      return (
        <div className="bg-blue-50 border border-blue-200 rounded-md p-3 max-w-sm">
          <div className="flex items-center gap-2 mb-2">
            <ClipboardList className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-medium text-blue-900">User Input Form</span>
          </div>
          <p className="text-xs text-blue-700 mb-2">
            {formSchema?.message || 'User input requested'}
          </p>
          <div className="flex flex-wrap gap-1">
            {formSchema?.fields?.map((f: { label: string; type: string; required?: boolean }, i: number) => (
              <span key={i} className="inline-flex items-center rounded border border-blue-300 bg-white px-1.5 py-0.5 text-[10px] text-blue-800">
                {f.label}
                {f.required && <span className="text-red-500 ml-0.5">*</span>}
              </span>
            ))}
          </div>
        </div>
      );
    } else {
      return <div>{entry.text}</div>;
    }
  } catch (error) {
    console.error("Error parsing entry text:", error);
    return <></>;
  }
}
