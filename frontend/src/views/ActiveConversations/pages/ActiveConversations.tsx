import { useToast } from "@/hooks/useToast";
import { ActiveConversation } from "@/interfaces/liveConversation.interface";
import { Transcript, TranscriptEntry, BackendTranscript } from "@/interfaces/transcript.interface";
import { conversationService } from "@/services/liveConversations";
import { useQuery } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { ConversationList } from "../components/ConversationList";
import { ActiveConversationDialog } from "../components/ActiveConversationDialog";
import { apiRequest } from "@/config/api";
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
  
    let backendData: BackendTranscript | null = null;
    try {
      backendData = await apiRequest<BackendTranscript>("get", `/conversations/${item.id}`);
      console.log("Backend conversation data:", backendData);
    } catch (error) {
      console.error("Failed to fetch full conversation details:", error);
    }
  
    if (backendData?.transcription) {
      try {
        transcriptArray = JSON.parse(backendData.transcription);
      } catch (e) {
        console.error("Failed to parse transcription JSON:", e);
      }
    }
    
    if (transcriptArray.length === 0) {
      const cachedTranscript = conversationService.getCachedTranscript(item.id);
      if (cachedTranscript && cachedTranscript.length > 0) {
        transcriptArray = cachedTranscript;
      } else if (typeof item.transcript === "string") {
        try {
          transcriptArray = JSON.parse(item.transcript);
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
    }
  
    const isCall = backendData?.recording_id !== null || item.type === "call";
    const durationString = backendData?.duration ? formatDuration(backendData.duration) : "0:00";
  
    const enrichedTranscript: Transcript = {
      id: item.id,
      audio: "",
      duration: backendData?.duration || 0,
      recording_id: backendData?.recording_id || (isCall ? item.id : null),
      create_time: backendData?.created_at || item.timestamp,
      timestamp: backendData?.conversation_date || item.timestamp,
      status: backendData?.status || item.status,
      transcription: transcriptArray,
      transcript: transcriptArray,
      metadata: {
        isCall,
        duration: durationString,
        title: item.id.slice(-4),
        topic: backendData?.analysis?.topic || `Active ${isCall ? "Call" : "Chat"}`,
        customer_speaker: "customer",
      },
      metrics: {
        sentiment: item.sentiment || "neutral",
        customerSatisfaction: backendData?.analysis?.customer_satisfaction || 0,
        serviceQuality: backendData?.analysis?.quality_of_service || 0,
        resolutionRate: backendData?.analysis?.resolution_rate || 0,
        speakingRatio: {
          agent: backendData?.agent_ratio || 0,
          customer: backendData?.customer_ratio || 0,
        },
        tone: backendData?.analysis?.tone ? [backendData.analysis.tone] : ["neutral"],
        wordCount: backendData?.word_count || 0,
        in_progress_hostility_score: backendData?.in_progress_hostility_score || item.in_progress_hostility_score || 0,
      },
      agent_ratio: backendData?.agent_ratio || 0,
      customer_ratio: backendData?.customer_ratio || 0, 
      word_count: backendData?.word_count || 0,
      in_progress_hostility_score: backendData?.in_progress_hostility_score || item.in_progress_hostility_score || 0,
    };
  
    console.log("Enriched transcript with stats:", enrichedTranscript);
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
