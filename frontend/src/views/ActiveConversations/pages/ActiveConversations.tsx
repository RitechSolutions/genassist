import { useToast } from "@/hooks/useToast";
import { ActiveConversation } from "@/interfaces/liveConversation.interface";
import { Transcript, TranscriptEntry, BackendTranscript } from "@/interfaces/transcript.interface";
import { conversationService } from "@/services/liveConversations";
import { useQuery } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { ConversationList } from "../components/ConversationList";
import { ActiveConversationDialog } from "../components/ActiveConversationDialog";
import { formatDuration } from "../helpers/format";

export const ActiveConversations = () => {
  const { toast } = useToast();
  const [selectedTranscript, setSelectedTranscript] = useState<Transcript | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const [socketData, setSocketData] = useState<{
    conversationId: string;
    token: string;
  } | null>(null);

  const {
    data: activeConversations,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ["activeConversations"],
    queryFn: () => conversationService.fetchActive(),
    refetchInterval: 5000,
    refetchOnWindowFocus: true,
    staleTime: 3000,
  });

  const handleItemClick = async (item: ActiveConversation) => {
    let transcriptArray: TranscriptEntry[] = [];
    const cachedTranscript = conversationService.getCachedTranscript(item.id);
    if (cachedTranscript && cachedTranscript.length > 0) {
      transcriptArray = cachedTranscript;
    } else if (typeof item.transcript === "string") {
      try {
        const parsed = JSON.parse(item.transcript);
        if (Array.isArray(parsed)) {
          transcriptArray = parsed;
        } else {
          transcriptArray = [
            {
              speaker: "customer",
              text: item.transcript,
              start_time: 0,
              end_time: 0,
              create_time: item.timestamp,
            },
          ];
        }
      } catch (e) {
        transcriptArray = [
          {
            speaker: "customer",
            text: item.transcript,
            start_time: 0,
            end_time: 0,
            create_time: item.timestamp,
          },
        ];
      }
    } else if (Array.isArray(item.transcript)) {
      transcriptArray = item.transcript as unknown as TranscriptEntry[];
    }
    
    const isCall = item.type === "call";
    const initialDurationInSeconds = typeof item.duration === 'number' ? item.duration : 0;
    const enrichedTranscript: Transcript = {
      id: item.id,
      audio: "",
      duration: initialDurationInSeconds,
      recording_id: isCall ? item.id : null,
      create_time: item.timestamp,
      timestamp: item.timestamp,
      status: item.status,
      transcription: transcriptArray,
      transcript: transcriptArray,
      metadata: {
        isCall,
        duration: initialDurationInSeconds,
        title: item.id.slice(-4),
        topic: `Active ${isCall ? "Call" : "Chat"}`,
        customer_speaker: "customer",
      },
      metrics: {
        sentiment: item.sentiment || "neutral",
        customerSatisfaction: 0,
        serviceQuality: 0,
        resolutionRate: 0,
        speakingRatio: {
          agent: item.agent_ratio || 0,
          customer: item.customer_ratio || 0,
        },
        tone: ["neutral"],
        wordCount: item.word_count || 0,
        in_progress_hostility_score: item.in_progress_hostility_score || 0,
      },
      agent_ratio: item.agent_ratio || 0,
      customer_ratio: item.customer_ratio || 0,
      word_count: item.word_count || 0,
      in_progress_hostility_score: item.in_progress_hostility_score || 0,
    };

    console.log("Enriched transcript with data from ActiveConversation item:", enrichedTranscript);
    setSelectedTranscript(enrichedTranscript);
    setIsDialogOpen(true);
  };

  const handleTakeOver = async (transcriptId: string): Promise<boolean> => {
    try {
      const success = await conversationService.takeoverConversation(
        transcriptId
      );
      if (success) {
        toast({
          title: "Success",
          description: "Successfully took over the conversation",
        });
        refetch();
      }
      return success;
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to take over conversation",
        variant: "destructive",
      });
      return false;
    }
  };

  const handleDialogClose = (open: boolean) => {
    setIsDialogOpen(open);
    if (!open) {
      refetch();
    }
  };

  const filteredConversations =
    activeConversations?.conversations?.filter(
      (conv) => conv.sentiment === "negative"
    ) ?? [];

  return (
    <>
      <ConversationList
        title="Active Conversations"
        viewAllLink="/transcripts?status=in_progress&status=takeover"
        items={filteredConversations}
        countDisplay={activeConversations?.total ?? 0}
        isLoading={isLoading}
        error={error as Error}
        onItemClick={handleItemClick}
        emptyMessage="No active conversations with issues at the moment"
        titleTooltip="Real-time conversations that require immediate attention due to negative sentiment"
      />

      <ActiveConversationDialog
        transcript={selectedTranscript}
        isOpen={isDialogOpen}
        onOpenChange={handleDialogClose}
        onTakeOver={handleTakeOver}
        refetchConversations={refetch}
      />
    </>
  );
};
