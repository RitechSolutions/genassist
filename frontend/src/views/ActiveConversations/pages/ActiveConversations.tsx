import { useToast } from "@/hooks/useToast";
import { ActiveConversation } from "@/interfaces/liveConversation.interface";
import { Transcript, TranscriptEntry } from "@/interfaces/transcript.interface";
import { conversationService } from "@/services/liveConversations";
import { fetchDashboardConversations } from "@/services/dashboard";
import { ActiveConversationItem } from "@/interfaces/dashboard.interface";
import { apiRequest } from "@/config/api";
import { BackendTranscript } from "@/interfaces/transcript.interface";
import { transformTranscript } from "@/views/Transcripts/helpers/transformers";
import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { ActiveConversationsModule } from "../components/ActiveConversationsModule";
import { HOSTILITY_NEUTRAL_MAX, HOSTILITY_POSITIVE_MAX } from "@/views/Transcripts/helpers/formatting";
import { ActiveConversationDialog } from "../components/ActiveConversationDialog";
import { useWebSocketDashboard } from "../hooks/useWebSocketDashboard";
import { YourAgentsCard } from "../components/YourAgentsCard";
import { IntegrationsCard } from "../components/IntegrationsCard";

// Transform dashboard API response to ActiveConversation format
const transformDashboardConversation = (item: ActiveConversationItem): ActiveConversation => ({
  id: item.id,
  type: "chat",
  status: item.status === "in_progress" ? "in-progress" : item.status,
  transcript: item.last_message || "",
  sentiment: item.feedback?.toLowerCase() === "good" ? "positive" :
             item.feedback?.toLowerCase() === "bad" ? "negative" : "neutral",
  timestamp: item.created_at,
  in_progress_hostility_score: item.in_progress_hostility_score || 0,
  duration: item.duration || 0,
  word_count: 0,
  agent_ratio: 0,
  customer_ratio: 0,
  supervisor_id: undefined,
  topic: item.topic || undefined,
  negative_reason: item.negative_reason || undefined,
});

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
  const [sentimentCounts, setSentimentCounts] = useState<{good: number; neutral: number; bad: number}>({good: 0, neutral: 0, bad: 0});
  const [isLoadingInitial, setIsLoadingInitial] = useState(true);
  const [apiError, setApiError] = useState<Error | null>(null);
  const DASHBOARD_LIMIT = 3;

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

  // Load conversations from dashboard API
  useEffect(() => {
    const loadConversations = async () => {
      try {
        setIsLoadingInitial(true);
        setApiError(null);

        // Use dashboard API for conversations (limited to 3 for dashboard view)
        const response = await fetchDashboardConversations(30, 1, DASHBOARD_LIMIT);
        if (response) {
          const transformed = response.conversations.map(transformDashboardConversation);
          setAllConversations(transformed);
          setTotalCount(response.total);
          setSentimentCounts({
            good: response.good_count ?? 0,
            neutral: response.neutral_count ?? 0,
            bad: response.bad_count ?? 0,
          });
        } else {
          setAllConversations([]);
        }
      } catch (error) {
        setApiError(error as Error);
      } finally {
        setIsLoadingInitial(false);
      }
    };

    loadConversations();
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

  // If the dashboard hook suggests resync (e.g., finalize with missing ID), refetch from dashboard API
  useEffect(() => {
    const sync = async () => {
      try {
        const response = await fetchDashboardConversations(30, 1, DASHBOARD_LIMIT);
        if (response) {
          const transformed = response.conversations.map(transformDashboardConversation);
          setAllConversations(transformed);
          setTotalCount(response.total);
          setSentimentCounts({
            good: response.good_count ?? 0,
            neutral: response.neutral_count ?? 0,
            bad: response.bad_count ?? 0,
          });
        }
      } catch (e) {
        // ignore
      }
    };
    if (resyncHint > 0) sync();
  }, [resyncHint, sentimentFilter, categoryFilter]);

  // Poll dashboard API for updates
  useEffect(() => {
    let isCancelled = false;

    const fetchData = async () => {
      try {
        const response = await fetchDashboardConversations(30, 1, DASHBOARD_LIMIT);
        if (!isCancelled && response) {
          const transformed = response.conversations.map(transformDashboardConversation);
          setAllConversations(transformed);
          setTotalCount(response.total);
          setSentimentCounts({
            good: response.good_count ?? 0,
            neutral: response.neutral_count ?? 0,
            bad: response.bad_count ?? 0,
          });
        }
      } catch (e) {
        // ignore
      }
    };

    const interval = setInterval(fetchData, 25000);
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
        // Update the selected transcript and list
        setSelectedTranscript((prev) =>
          prev?.id === transcriptId
            ? { ...prev, status: "takeover" as const }
            : prev
        );
        setAllConversations((prev) =>
          prev.map((c) =>
            c.id === transcriptId ? { ...c, status: "takeover" as const } : c
          )
        );
        wsRefetch();
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
        sentimentCounts={sentimentCounts}
      />

      {/* Your Agents and Integrations Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">
        <YourAgentsCard />
        <IntegrationsCard />
      </div>

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
