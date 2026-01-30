import { useToast } from "@/hooks/useToast";
import { ActiveConversation } from "@/interfaces/liveConversation.interface";
import { Transcript, TranscriptEntry } from "@/interfaces/transcript.interface";
import { conversationService } from "@/services/liveConversations";
import { apiRequest } from "@/config/api";
import { BackendTranscript } from "@/interfaces/transcript.interface";
import { transformTranscript } from "@/views/Transcripts/helpers/transformers";
import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { ActiveConversationsModule } from "../components/ActiveConversationsModule";
import { HOSTILITY_NEUTRAL_MAX, HOSTILITY_POSITIVE_MAX } from "@/views/Transcripts/helpers/formatting";
import { ActiveConversationDialog } from "../components/ActiveConversationDialog";
import { useWebSocketDashboard } from "../hooks/useWebSocketDashboard";

const enrichConversationItem = (item: ActiveConversation): Transcript => {
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
  const initialDurationInSeconds = typeof item.duration === "number" ? item.duration : 0;
  
  return {
    id: item.id,
    audio: "",
    duration: initialDurationInSeconds,
    recording_id: isCall ? item.id : null,
    create_time: item.timestamp,
    timestamp: item.timestamp,
    status: item.status,
    transcription: transcriptArray,
    messages: transcriptArray,
    supervisor_id: item.supervisor_id,
    metadata: {
      isCall,
      duration: initialDurationInSeconds,
      title: item.id.slice(-4),
      topic: item.topic || `Active ${isCall ? "Call" : "Chat"}`,
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
};

export const ActiveConversations = () => {
  const { toast } = useToast();
  const [searchParams] = useSearchParams();
  const [selectedTranscript, setSelectedTranscript] = useState<Transcript | null>(
    null
  );
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isLoadingTranscript, setIsLoadingTranscript] = useState(false);
  const [allConversations, setAllConversations] = useState<ActiveConversation[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [isLoadingInitial, setIsLoadingInitial] = useState(true);
  const [apiError, setApiError] = useState<Error | null>(null);

  // Get access token for WebSocket authentication
  const accessToken = localStorage.getItem("access_token");

  // Get current filter parameters from URL
  const sentimentFilter = searchParams.get("sentiment") || undefined;
  const categoryFilter = searchParams.get("category") || undefined;
  const includeFeedbackFilter = (searchParams.get("include_feedback") || "false").toLowerCase() === "true";

  // Use WebSocket hook for real-time updates
  const {
    conversations: wsConversations,
    total: wsTotal,
    isConnected,
    error: wsError,
    refetch: wsRefetch,
    resyncHint,
  } = useWebSocketDashboard({
    token: accessToken || "",
    lang: "en",
    topics: ["message", "statistics", "finalize", "hostile"]
  });

  // Load initial conversations from API with filter support
  useEffect(() => {
    const loadInitialConversations = async () => {
      try {
        setIsLoadingInitial(true);
        setApiError(null);
        
        const response = await conversationService.fetchActive({
          sentiment: sentimentFilter,
          category: categoryFilter,
          hostility_positive_max: HOSTILITY_POSITIVE_MAX,
          hostility_neutral_max: HOSTILITY_NEUTRAL_MAX,
          include_feedback: includeFeedbackFilter,
        });
        setAllConversations(response.conversations || []);
        // Do not update totalCount here; total comes from polling only
      } catch (error) {
        setApiError(error as Error);
      } finally {
        setIsLoadingInitial(false);
      }
    };

    loadInitialConversations();
  }, [sentimentFilter, categoryFilter]); // Reload when filters change

  // Merge WebSocket updates with existing conversations
  useEffect(() => {
    if (wsConversations !== undefined) {
      
      // Merge without removing existing items; finalization will explicitly remove
      setAllConversations(prev => {
        if (!Array.isArray(wsConversations) || wsConversations.length === 0) return prev;
        const map = new Map(prev.map(c => [c.id, c] as const));
        for (const wsConv of wsConversations) map.set(wsConv.id, wsConv);
        return Array.from(map.values());
      });
    }
  }, [wsConversations]);

  // If the dashboard hook suggests resync (e.g., finalize with missing ID), refetch from API
  useEffect(() => {
    const sync = async () => {
      try {
        const response = await conversationService.fetchActive({
          sentiment: sentimentFilter,
          category: categoryFilter,
          hostility_positive_max: HOSTILITY_POSITIVE_MAX,
          hostility_neutral_max: HOSTILITY_NEUTRAL_MAX,
          include_feedback: includeFeedbackFilter,
        });
        setAllConversations(response.conversations || []);
      } catch (e) {
        // ignore
      }
    };
    if (resyncHint > 0) sync();
  }, [resyncHint, sentimentFilter, categoryFilter]);

  // Poll backend every 5s
  useEffect(() => {
    let isCancelled = false;

    const fetchCount = async () => {
      try {
        const count = await conversationService.fetchInProgressCount();
        if (!isCancelled && typeof count === "number") {
          setTotalCount(count);
        }
      } catch (e) {
        // ignore
      }
    };
    fetchCount();

    const interval = setInterval(fetchCount, 25000);
    return () => {
      isCancelled = true;
      clearInterval(interval);
    };
  }, []);

  // Error handling - prioritize API errors over WebSocket errors
  const error = apiError || wsError;
  // Main loading is driven by HTTP snapshot only
  const isLoading = isLoadingInitial;

  useEffect(() => {
    if (!isDialogOpen || !selectedTranscript?.id || !allConversations) return;

    const normalizeStatus = (s?: string | null): string => {
      if (!s) return "";
      const v = s.toLowerCase();
      if (v === "in_progress" || v === "in-progress") return "in-progress";
      if (v === "takeover") return "takeover";
      return v;
    };

    const fresh = allConversations.find((c) => c.id === selectedTranscript.id);
    if (!fresh) return;

    const freshStatus = normalizeStatus(fresh.status as unknown as string);
    const selectedStatus = normalizeStatus(selectedTranscript.status);
    const freshSupervisor = fresh.supervisor_id ?? null;
    const selectedSupervisor = selectedTranscript.supervisor_id ?? null;

    if (freshStatus !== selectedStatus || freshSupervisor !== selectedSupervisor) {
      handleItemClick(fresh);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allConversations, selectedTranscript?.id, selectedTranscript?.status, selectedTranscript?.supervisor_id, isDialogOpen]);

  const handleItemClick = async (item: ActiveConversation) => {
    setIsLoadingTranscript(true);
    
    try {
      // Fetch the full  conversation data by ID
      const backend = await apiRequest<BackendTranscript>("get", `/conversations/${item.id}?include_feedback=true`);
      const transformed = transformTranscript(backend);
      if (item.topic && item.topic !== "Unknown" && transformed?.metadata) {
        transformed.metadata.topic = transformed.metadata.topic && transformed.metadata.topic !== "Unknown"
          ? transformed.metadata.topic
          : item.topic;
      }
      setSelectedTranscript(transformed);
      setIsDialogOpen(true);
      
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load conversation details",
        variant: "destructive",
      });
      
      // Fallback to enriched conversation item if fetch fails
      const enrichedTranscript = enrichConversationItem(item);
      setSelectedTranscript(enrichedTranscript);
      setIsDialogOpen(true);
    } finally {
      setIsLoadingTranscript(false);
    }
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
        // Refresh both API data and WebSocket
        wsRefetch();
        // Also reload API data to ensure consistency
        const response = await conversationService.fetchActive({
          sentiment: sentimentFilter,
          category: categoryFilter,
          include_feedback: includeFeedbackFilter,
        });
        setAllConversations(response.conversations || []);
        // Total comes from polling only
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
      wsRefetch();
    }
  };

  const filteredConversations = allConversations ?? [];

  return (
    <>
      <ActiveConversationsModule
        items={filteredConversations}
        isLoading={isLoading}
        error={error as Error}
        onRetry={wsRefetch}
        onItemClick={handleItemClick}
        totalCount={totalCount}
      />

      <ActiveConversationDialog
        transcript={selectedTranscript}
        isOpen={isDialogOpen}
        onOpenChange={handleDialogClose}
        onTakeOver={handleTakeOver}
        refetchConversations={wsRefetch}
      />
    </>
  );
};
