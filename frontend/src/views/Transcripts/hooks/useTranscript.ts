import { useState } from 'react';
import { useTranscriptData } from './useTranscriptData';
import type { Transcript } from '@/interfaces/transcript.interface';

export const useTranscript = (id: string) => {
  const { data, loading, error, refetch } = useTranscriptData({ id });
  const [chatMessages, setChatMessages] = useState<{ role: string; text: string }[]>([]);
  
  const transcript = data as Transcript;

  const addChatMessage = (role: string, text: string) => {
    setChatMessages(prev => [...prev, { role, text }]);
  };

  return {
    transcript,
    loading,
    error,
    refreshTranscript: refetch,
    chatMessages,
    addChatMessage
  };
}; 