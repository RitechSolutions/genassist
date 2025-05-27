import Transcripts from './pages/Transcripts';
import { RecentTranscripts } from './components/RecentTranscripts';
import { TranscriptDialog } from './components/TranscriptDialog';
import { TranscriptCard } from './components/TranscriptCard';
import { useTranscriptData } from './hooks/useTranscriptData';
import { useTranscripts } from './hooks/useTranscripts';
import { useTranscript } from './hooks/useTranscript';

export {
  RecentTranscripts,
  TranscriptDialog,
  TranscriptCard,
  useTranscriptData,
  useTranscripts,
  useTranscript
};

export default Transcripts; 