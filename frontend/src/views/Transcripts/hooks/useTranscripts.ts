import { useState } from 'react';
import { useTranscriptData } from './useTranscriptData';
import type { Transcript } from '@/interfaces/transcript.interface';

interface UseTranscriptsOptions {
  limit?: number;
  sortNewestFirst?: boolean;
}

export const useTranscripts = (options: UseTranscriptsOptions = {}) => {
  const { limit, sortNewestFirst = true } = options;
  
  const { data, loading, error, refetch } = useTranscriptData({ limit, sortNewestFirst });
  const [selectedTranscript, setSelectedTranscript] = useState<Transcript | null>(null);

  const transcripts = Array.isArray(data) ? data : [];

  return {
    transcripts,
    loading,
    error,
    selectedTranscript,
    setSelectedTranscript,
    refreshTranscripts: refetch
  };
}; 