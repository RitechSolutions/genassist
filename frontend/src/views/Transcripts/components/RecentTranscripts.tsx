import { useState } from "react";
import { Card } from "@/components/card";
import { TranscriptDialog } from "./TranscriptDialog";
import { ActiveConversationDialog } from "@/views/ActiveConversations/components/ActiveConversationDialog";
import { TranscriptCard } from "./TranscriptCard";
import { useTranscripts } from "../hooks/useTranscripts";
import type { Transcript } from "@/interfaces/transcript.interface";
import { CardHeader } from "@/components/CardHeader";

export function RecentTranscripts() {
  const { transcripts, loading, error, refreshTranscripts } = useTranscripts({ limit: 5, sortNewestFirst: true });
  const [selectedTranscript, setSelectedTranscript] = useState<Transcript | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isLiveTranscriptSelected, setIsLiveTranscriptSelected] = useState(false);

  const isLiveTranscript = (transcript: Transcript) => {
    return transcript?.status === "in_progress" || transcript?.status === "takeover";
  };

  const handleTranscriptClick = (transcript: Transcript) => {
    setSelectedTranscript(transcript);
    setIsLiveTranscriptSelected(isLiveTranscript(transcript));
    setIsModalOpen(true);
  };

  return (
    <>
      <Card className="p-6 shadow-sm transition-shadow hover:shadow-md animate-fade-up bg-white">
        <CardHeader 
          title="Recent Transcripts"
          tooltipText="The most recent customer interactions with detailed conversation transcripts and analytics"
          linkText="View all"
          linkHref="/transcripts"
        />
        <div className="space-y-4">
          {loading ? (
            <div className="p-4 text-center text-muted-foreground">
              Loading transcripts...
            </div>
          ) : error ? (
            <div className="p-4 text-center text-red-500">
              Failed to load transcripts. Please try again.
            </div>
          ) : transcripts.length > 0 ? (
            transcripts.map((transcript) => (
              <TranscriptCard 
                key={transcript.id} 
                transcript={transcript} 
                onClick={handleTranscriptClick} 
              />
            ))
          ) : (
            <div className="p-4 text-center text-muted-foreground">
              No recent transcripts found.
            </div>
          )}
        </div>
      </Card>

      {isLiveTranscriptSelected ? (
        <ActiveConversationDialog 
          transcript={selectedTranscript} 
          isOpen={isModalOpen} 
          onOpenChange={setIsModalOpen}
          refetchConversations={refreshTranscripts}
        />
      ) : (
        <TranscriptDialog 
          transcript={selectedTranscript} 
          isOpen={isModalOpen} 
          onOpenChange={setIsModalOpen} 
        />
      )}
    </>
  );
}