import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import toast from "react-hot-toast";

import { isWsEnabled } from "@/config/api";
import { DEFAULT_LLM_ANALYST_ID } from "@/constants/llmAnalyst";
import { Transcript, TranscriptEntry } from "@/interfaces/transcript.interface";
import { getCurrentUserId } from "@/services/auth";
import { conversationService } from "@/services/liveConversations";
import { getSentimentFromHostility } from "@/views/Transcripts/helpers/formatting";

import { useWebSocketTranscript } from "./useWebsocket";

export interface ConversationStats {
  agent_ratio?: number;
  customer_ratio?: number;
  duration?: number;
  in_progress_hostility_score?: number;
  word_count?: number;
  topic?: string;
  sentiment?: string;
}

function toEpochMs(ct: string | number | undefined | null): number {
  if (ct == null) return 0;
  if (typeof ct === "number") return ct;
  const t = new Date(ct).getTime();
  return isNaN(t) ? 0 : t;
}

function areMessagesEquivalent(
  previous: TranscriptEntry[],
  next: TranscriptEntry[]
): boolean {
  if (previous === next) return true;
  if (previous.length !== next.length) return false;

  for (let index = 0; index < previous.length; index += 1) {
    const prevMsg = previous[index];
    const nextMsg = next[index];

    if (
      prevMsg.type !== nextMsg.type ||
      prevMsg.speaker !== nextMsg.speaker ||
      prevMsg.text !== nextMsg.text ||
      toEpochMs(prevMsg.create_time) !== toEpochMs(nextMsg.create_time)
    ) {
      return false;
    }
  }

  return true;
}

interface UseActiveConversationDetailOptions {
  transcript: Transcript;
  /** The detail surface is visible — a dialog that is open, or a mounted pane. */
  isActive: boolean;
  onTakeOver?: (transcriptId: string) => Promise<boolean>;
  refetchConversations?: () => void;
  /** Messages pushed in by the parent (dashboard websocket) on top of the transcript. */
  messages?: TranscriptEntry[];
  /** Fired as soon as finalizing starts — the dialog uses it to close itself. */
  onFinalizeStart?: () => void;
  /**
   * Fired once the conversation is finalized on the server. Awaited, so `isFinalizing` (and
   * with it the caller's busy state) stays up until the caller has swapped in the finalized
   * surface — otherwise the live view lingers until a manual refresh.
   */
  onFinalized?: (transcriptId: string) => void | Promise<void>;
}

/**
 * Everything `ActiveConversationDialog` used to own: live websocket messages, running
 * statistics, takeover state and the supervisor composer.
 *
 * Conversation feedback is deliberately absent — a conversation is only rated once it is
 * finalized, which is `useTranscriptDetail`'s surface.
 *
 * Extracted so the same live conversation can render either as a dialog or as the detail
 * columns of the Conversations workspace.
 */
export function useActiveConversationDetail({
  transcript,
  isActive,
  onTakeOver,
  refetchConversations,
  messages = [],
  onFinalizeStart,
  onFinalized,
}: UseActiveConversationDetailOptions) {
  const transcriptMessages = useMemo(() => {
    const raw = transcript?.messages ?? transcript?.transcript;
    return Array.isArray(raw) ? raw : [];
  }, [transcript?.messages, transcript?.transcript]);
  const incomingMessages = useMemo(
    () => (Array.isArray(messages) ? messages : []),
    [messages]
  );

  const hasSupervisorTakeover = useMemo(() => {
    if (!transcript) return false;
    return (
      transcript.status === "takeover" ||
      transcriptMessages.some((entry) => entry.type === "takeover")
    );
  }, [transcript?.status, transcriptMessages]);

  const [userInitiatedTakeOver, setUserInitiatedTakeOver] = useState(false);
  const [localSupervisorId, setLocalSupervisorId] = useState<string | null>(null);
  const currentUserId = getCurrentUserId();
  const [chatInput, setChatInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [localMessages, setLocalMessages] = useState<TranscriptEntry[]>(
    () => transcriptMessages
  );
  const [sentMessages, setSentMessages] = useState<TranscriptEntry[]>([]);
  const isSendingRef = useRef(false);
  const [isThinking, setIsThinking] = useState(false);

  const [conversationStats, setConversationStats] = useState<ConversationStats>(
    () => {
      return {
        agent_ratio:
          transcript?.agent_ratio ??
          transcript?.metrics?.speakingRatio?.agent ??
          0,
        customer_ratio:
          transcript?.customer_ratio ??
          transcript?.metrics?.speakingRatio?.customer ??
          0,
        duration: transcript?.duration ?? 0,
        in_progress_hostility_score:
          transcript?.in_progress_hostility_score ??
          transcript?.metrics?.in_progress_hostility_score ??
          0,
        word_count:
          transcript?.word_count ?? transcript?.metrics?.wordCount ?? 0,
        topic: transcript?.metadata?.topic,
        sentiment: transcript?.metrics?.sentiment,
      };
    }
  );

  const scrollRef = useRef<HTMLDivElement>(null);
  const token = localStorage.getItem("access_token") || "";

  useEffect(() => {
    if (!isActive) {
      setUserInitiatedTakeOver(false);
      setLocalSupervisorId(null);
    }
  }, [isActive]);

  useEffect(() => {
    setUserInitiatedTakeOver(false);
    setLocalSupervisorId(null);
  }, [transcript?.id]);

  const shouldInitWebSocket = isWsEnabled && transcript?.id && token;

  const {
    messages: wsMessages,
    isConnected,
    statistics,
    takeoverInfo,
  } = useWebSocketTranscript(
    shouldInitWebSocket
      ? {
          conversationId: transcript.id,
          token,
          transcriptInitial: transcriptMessages,
        }
      : {
          conversationId: "",
          token: "",
          transcriptInitial: [],
        }
  );

  useEffect(() => {
    if (takeoverInfo.supervisor_id) {
      setLocalSupervisorId(takeoverInfo.supervisor_id);
    }
  }, [takeoverInfo.supervisor_id]);

  const resolvedSupervisorId = useMemo(() => {
    const fromTranscript = transcript?.supervisor_id?.trim();
    return (
      localSupervisorId ??
      (fromTranscript || null) ??
      takeoverInfo.supervisor_id ??
      null
    );
  }, [localSupervisorId, transcript?.supervisor_id, takeoverInfo.supervisor_id]);

  const isCurrentUserSupervisor = useMemo(() => {
    if (userInitiatedTakeOver) return true;
    if (!hasSupervisorTakeover) return false;
    if (!currentUserId || !resolvedSupervisorId) return false;
    return resolvedSupervisorId === currentUserId;
  }, [
    userInitiatedTakeOver,
    hasSupervisorTakeover,
    currentUserId,
    resolvedSupervisorId,
  ]);

  const isTakenOverByOther = hasSupervisorTakeover && !isCurrentUserSupervisor;

  const supervisorDisplayName = useMemo(() => {
    const fromApi = transcript?.supervisor_username?.trim();
    if (fromApi) return fromApi;
    if (resolvedSupervisorId) {
      return `Supervisor (${resolvedSupervisorId.slice(-4)})`;
    }
    return "Another supervisor";
  }, [transcript?.supervisor_username, resolvedSupervisorId]);

  useEffect(() => {
    if (transcript) {
      setConversationStats({
        agent_ratio:
          transcript.agent_ratio ??
          transcript.metrics?.speakingRatio?.agent ??
          0,
        customer_ratio:
          transcript.customer_ratio ??
          transcript.metrics?.speakingRatio?.customer ??
          0,
        duration: transcript.duration ?? 0,
        in_progress_hostility_score:
          transcript.in_progress_hostility_score ??
          transcript.metrics?.in_progress_hostility_score ??
          0,
        word_count: transcript.word_count ?? transcript.metrics?.wordCount ?? 0,
        topic: transcript.metadata?.topic,
        sentiment: transcript.metrics?.sentiment,
      });
    }
  }, [transcript]);

  useEffect(() => {
    if (statistics && transcript?.id) {
      setConversationStats((prevStats) => {
        const newStats = { ...prevStats };
        let hasUpdates = false;

        if (
          typeof statistics.agent_ratio === "number" &&
          newStats.agent_ratio !== statistics.agent_ratio
        ) {
          newStats.agent_ratio = Number(statistics.agent_ratio);
          hasUpdates = true;
        }

        if (
          typeof statistics.customer_ratio === "number" &&
          newStats.customer_ratio !== statistics.customer_ratio
        ) {
          newStats.customer_ratio = Number(statistics.customer_ratio);
          hasUpdates = true;
        }

        if (
          typeof statistics.duration === "number" &&
          newStats.duration !== statistics.duration
        ) {
          newStats.duration = Number(statistics.duration);
          hasUpdates = true;
        }

        if (
          typeof statistics.in_progress_hostility_score === "number" &&
          newStats.in_progress_hostility_score !==
            statistics.in_progress_hostility_score
        ) {
          newStats.in_progress_hostility_score = Number(
            statistics.in_progress_hostility_score
          );
          hasUpdates = true;
        }

        if (
          typeof statistics.word_count === "number" &&
          newStats.word_count !== statistics.word_count
        ) {
          newStats.word_count = Number(statistics.word_count);
          hasUpdates = true;
        }

        if (
          typeof statistics.topic === "string" &&
          newStats.topic !== statistics.topic
        ) {
          newStats.topic = statistics.topic;
          hasUpdates = true;
        }
        if (
          typeof statistics.sentiment === "string" &&
          newStats.sentiment !== statistics.sentiment
        ) {
          newStats.sentiment = statistics.sentiment;
          hasUpdates = true;
        }

        if (hasUpdates) {
          return newStats;
        }

        return prevStats;
      });
    }
  }, [statistics, transcript?.id]);

  useEffect(() => {
    if (!isActive) {
      setChatInput("");
    }
  }, [isActive]);

  useEffect(() => {
    if (!isActive) return;

    // Base messages from transcript (so refetched data from parent is always used)
    const currentMsgs: TranscriptEntry[] = [...transcriptMessages];

    if (wsMessages.length > 0) {
      for (const msg of wsMessages) {
        const speaker = msg?.speaker?.toLowerCase();
        if (speaker === "customer" && !isCurrentUserSupervisor) {
          setIsThinking(true);
        }

        if (speaker === "agent") {
          setIsThinking(false);
        }

        if (
          !currentMsgs.some(
            (m) =>
              m.text === msg.text &&
              toEpochMs(m.create_time) === toEpochMs(msg.create_time)
          )
        ) {
          currentMsgs.push(msg);
        }
      }
    }

    if (incomingMessages.length > 0) {
      for (const msg of incomingMessages) {
        if (
          !currentMsgs.some(
            (m) =>
              m.text === msg.text &&
              toEpochMs(m.create_time) === toEpochMs(msg.create_time)
          )
        ) {
          currentMsgs.push(msg);
        }
      }
    }

    for (const sentMsg of sentMessages) {
      if (
        !currentMsgs.some(
          (m) =>
            m.text === sentMsg.text &&
            toEpochMs(m.create_time) === toEpochMs(sentMsg.create_time)
        )
      ) {
        currentMsgs.push(sentMsg);
      }
    }

    if (
      transcript?.status === "takeover" &&
      !currentMsgs.some((m) => m.type === "takeover")
    ) {
      const now = Date.now();
      const conversationCreateTime = transcript.create_time
        ? new Date(transcript.create_time).getTime()
        : now;
      currentMsgs.push({
        speaker: "", // no speaker shown in UI for takeover marker
        text: "", // handled specially in renderer
        start_time: (now - conversationCreateTime) / 1000,
        end_time: (now - conversationCreateTime) / 1000,
        create_time: new Date(now).toISOString(),
        type: "takeover",
      } as TranscriptEntry);
    }

    // Ensure at most one takeover marker (stale closure can cause duplicates)
    let seenTakeover = false;
    const dedupedMsgs = currentMsgs.filter((m) => {
      if (m.type === "takeover") {
        if (seenTakeover) return false;
        seenTakeover = true;
      }
      return true;
    });

    setLocalMessages((prevMessages) =>
      areMessagesEquivalent(prevMessages, dedupedMsgs)
        ? prevMessages
        : dedupedMsgs
    );
  }, [
    transcriptMessages,
    transcript,
    wsMessages,
    incomingMessages,
    sentMessages,
    isActive,
    isCurrentUserSupervisor,
  ]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [localMessages]);

  const socketHostility =
    typeof statistics?.in_progress_hostility_score === "number"
      ? Number(statistics.in_progress_hostility_score)
      : undefined;
  const currentHostility =
    socketHostility ??
    Number(
      conversationStats.in_progress_hostility_score ??
        transcript.metrics?.in_progress_hostility_score ??
        transcript.in_progress_hostility_score ??
        0
    );
  const sentiment = getSentimentFromHostility(currentHostility || 0);
  const hostilityScore = currentHostility ?? 0;
  const liveTopic =
    typeof statistics?.topic === "string" && statistics.topic.trim() !== ""
      ? statistics.topic
      : undefined;
  const topicText =
    liveTopic ||
    conversationStats.topic ||
    transcript.metadata?.topic ||
    "Active Conversation";

  const handleTakeOver = useCallback(async () => {
    if (!transcript?.id) return;
    setLoading(true);
    try {
      const success = onTakeOver
        ? await onTakeOver(transcript.id)
        : await conversationService.takeoverConversation(transcript.id);

      if (success) {
        setIsThinking(false);
        setUserInitiatedTakeOver(true);
        const uid = getCurrentUserId();
        if (uid) setLocalSupervisorId(uid);

        const now = Date.now();
        const conversationCreateTime = transcript.create_time
          ? new Date(transcript.create_time).getTime()
          : now;
        const takeoverEntry: TranscriptEntry = {
          speaker: "",
          text: "",
          start_time: (now - conversationCreateTime) / 1000,
          end_time: (now - conversationCreateTime) / 1000,
          create_time: new Date(now).toISOString(),
          type: "takeover",
        };

        setLocalMessages((prev) =>
          prev.some((m) => m.type === "takeover")
            ? prev
            : [...prev, takeoverEntry]
        );

        if (refetchConversations) {
          refetchConversations();
        }
      }
    } catch {
      // surfaced by the caller's own toast
    } finally {
      setLoading(false);
    }
  }, [transcript, onTakeOver, refetchConversations]);

  const durationInSeconds =
    conversationStats.duration > 3600 * 24
      ? Math.floor(conversationStats.duration / 1000)
      : conversationStats.duration;

  const handleSendMessage = useCallback(async () => {
    if (!chatInput.trim() || !transcript?.id || isSendingRef.current) return;

    isSendingRef.current = true;

    const now = Date.now();
    const conversationCreateTime = transcript.create_time
      ? new Date(transcript.create_time).getTime()
      : now;
    const newEntry: TranscriptEntry = {
      speaker: "agent",
      text: chatInput.trim(),
      start_time: (now - conversationCreateTime) / 1000,
      end_time: (now - conversationCreateTime) / 1000 + 0.01,
      create_time: new Date(now).toISOString(),
    };

    setChatInput("");

    // Add message to local state immediately for instant UI feedback
    setSentMessages((prev) => [...prev, newEntry]);

    try {
      await conversationService.updateConversation(transcript.id, {
        messages: [newEntry],
        llm_analyst_id: DEFAULT_LLM_ANALYST_ID,
      });

      if (refetchConversations) refetchConversations();
    } catch {
      // Remove the message from sent messages if the API call fails
      setSentMessages((prev) =>
        prev.filter((m) => m.create_time !== newEntry.create_time)
      );
      toast.error("Failed to send message");
    } finally {
      isSendingRef.current = false;
    }
  }, [chatInput, transcript, refetchConversations]);

  const handleFinalize = useCallback(async () => {
    if (!transcript?.id) return;

    setIsFinalizing(true);
    onFinalizeStart?.();

    const processingToast = toast.loading("Processing conversation...", {
      duration: Infinity,
    });

    try {
      await conversationService.finalizeConversation(transcript.id);
      toast.dismiss(processingToast);
      toast.success("Conversation finalized successfully.");
      if (refetchConversations) refetchConversations();
      await onFinalized?.(transcript.id);
    } catch {
      toast.dismiss(processingToast);
      toast.error("Failed to finalize conversation.");
    } finally {
      setIsFinalizing(false);
    }
  }, [transcript?.id, onFinalizeStart, onFinalized, refetchConversations]);

  return {
    transcript,
    messages: localMessages,
    scrollRef,
    isConnected,
    isThinking,
    conversationStats,
    durationInSeconds,
    hostilityScore,
    sentiment,
    topicText,
    hasSupervisorTakeover,
    isCurrentUserSupervisor,
    isTakenOverByOther,
    supervisorDisplayName,
    chatInput,
    setChatInput,
    loading,
    isFinalizing,
    handleTakeOver,
    handleSendMessage,
    handleFinalize,
  };
}

export type ActiveConversationDetailController = ReturnType<
  typeof useActiveConversationDetail
>;
