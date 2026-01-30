import {
  Timer,
  MessageSquare,
  AlertTriangle,
  User,
  Frown,
  MessageCircle,
  ThumbsUp,
  ThumbsDown,
  Pencil,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Transcript,
  TranscriptEntry,
  ConversationFeedbackEntry,
} from "@/interfaces/transcript.interface";
import { Input } from "@/components/input";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { conversationService } from "@/services/liveConversations";
import { useWebSocketTranscript } from "../hooks/useWebsocket";
import { DEFAULT_LLM_ANALYST_ID } from "@/constants/llmModels";
import toast from "react-hot-toast";
import { formatDuration, formatMessageTime } from "../helpers/format";
import { Tabs, TabsList, TabsTrigger } from "@/components/tabs";
import { Textarea } from "@/components/textarea";
import { submitConversationFeedback } from "@/services/transcripts";
import { apiRequest, isWsEnabled } from "@/config/api";
import { BackendTranscript } from "@/interfaces/transcript.interface";
import { getSentimentFromHostility } from "@/views/Transcripts/helpers/formatting";
import { ConversationEntryWrapper } from "@/views/ActiveConversations/common/ConversationEntryWrapper";

interface Props {
  transcript: Transcript | null;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onTakeOver?: (transcriptId: string) => Promise<boolean>;
  refetchConversations?: () => void;
  isWebSocketConnected?: boolean;
  messages?: TranscriptEntry[];
  onSendMessage?: (message: TranscriptEntry) => void;
  isFinalized?: boolean;
  hasSupervisorTakeover?: boolean;
}

interface ConversationStats {
  agent_ratio?: number;
  customer_ratio?: number;
  duration?: number;
  in_progress_hostility_score?: number;
  word_count?: number;
  topic?: string;
  sentiment?: string;
}

export function ActiveConversationDialog({
  transcript,
  isOpen,
  onOpenChange,
  onTakeOver,
  refetchConversations,
  messages = [],
}: Props) {
  if (!transcript) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <TranscriptDialogContent
          key={`transcript-dialog-${transcript.id}`}
          transcript={transcript}
          isOpen={isOpen}
          onOpenChange={onOpenChange}
          onTakeOver={onTakeOver}
          refetchConversations={refetchConversations}
          messages={messages}
        />
      </DialogContent>
    </Dialog>
  );
}

function TranscriptDialogContent({
  transcript,
  isOpen,
  onOpenChange,
  onTakeOver,
  refetchConversations,
  messages = [],
}: Props): JSX.Element {
  const feedbackCacheRef = useRef<Map<string, ConversationFeedbackEntry>>(
    new Map()
  );
  const hasSupervisorTakeover = useMemo(() => {
    if (!transcript) return false;
    return (
      transcript.status === "takeover" ||
      ((transcript.messages ?? transcript.transcript) ?? []).some((entry) => entry.type === "takeover")
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transcript?.status, transcript?.transcript]);

  const [hasTakenOver, setHasTakenOver] = useState(hasSupervisorTakeover);
  const [userInitiatedTakeOver, setUserInitiatedTakeOver] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [localMessages, setLocalMessages] = useState<TranscriptEntry[]>(
    (transcript?.messages ?? transcript?.transcript) || []
  );
  const [sentMessages, setSentMessages] = useState<TranscriptEntry[]>([]);
  const [isThinking, setIsThinking] = useState(false);

  // Feedback state (conversation-level)
  const [leftPanelTab, setLeftPanelTab] = useState<"stats" | "feedback">(
    "stats"
  );
  const [feedbackType, setFeedbackType] = useState<"good" | "bad" | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [userFeedback, setUserFeedback] =
    useState<ConversationFeedbackEntry | null>(null);

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
    if (!isOpen) {
      setUserInitiatedTakeOver(false);
    }
  }, [isOpen]);

  useEffect(() => {
    if (userInitiatedTakeOver) {
      setHasTakenOver(true);
    }
  }, [userInitiatedTakeOver]);

  const shouldInitWebSocket = isWsEnabled && transcript?.id && token;

  const {
    messages: wsMessages,
    isConnected,
    sendMessage,
    statistics,
  } = useWebSocketTranscript(
    shouldInitWebSocket
      ? {
          conversationId: transcript.id,
          token,
          transcriptInitial: (transcript?.messages ?? transcript?.transcript) || [],
        }
      : {
          conversationId: "",
          token: "",
          transcriptInitial: [],
        }
  );

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
    if (!isOpen) {
      setChatInput("");
    }
  }, [isOpen]);

  const feedbackCount = Array.isArray(transcript?.feedback)
    ? transcript.feedback.length
    : 0;
  useEffect(() => {
    if (!isOpen) return;
    if (Array.isArray(transcript?.feedback) && transcript.feedback.length > 0) {
      const latest = transcript.feedback[transcript.feedback.length - 1];
      setUserFeedback(latest);
      try {
        feedbackCacheRef.current.set(transcript.id, latest);
      } catch {}
    } else if (transcript?.id) {
      const cached = feedbackCacheRef.current.get(transcript.id) || null;
      if (cached) setUserFeedback(cached);
    }
    // Do not clear when backend lacks feedback; use cached value if present
  }, [isOpen, feedbackCount]);

  // Fetch conversation by id to hydrate feedback if not present on the provided transcript
  useEffect(() => {
    if (!isOpen || !transcript?.id) return;
    if (userFeedback) return;
    (async () => {
      try {
        const raw = await apiRequest<BackendTranscript>(
          "get",
          `/conversations/${transcript.id}`
        );
        if (!raw) return;
        let fb: ConversationFeedbackEntry[] | undefined;
        if ((raw as unknown as { feedback?: unknown }).feedback) {
          const f = (raw as unknown as { feedback?: unknown })
            .feedback as unknown;
          if (typeof f === "string") {
            try {
              const parsed = JSON.parse(f);
              if (Array.isArray(parsed))
                fb = parsed as ConversationFeedbackEntry[];
            } catch {}
          } else if (Array.isArray(f)) {
            fb = f as ConversationFeedbackEntry[];
          }
        }
        if (fb && fb.length > 0) {
          const latest = fb[fb.length - 1];
          setUserFeedback(latest);
          try {
            feedbackCacheRef.current.set(transcript.id, latest);
          } catch {}
        }
      } catch {}
    })();
  }, [isOpen, transcript?.id, userFeedback]);

  useEffect(() => {
    if (isOpen && transcript) {
      const baseMessages = [...(((transcript.messages ?? transcript.transcript) || []))];

      for (const sentMsg of sentMessages) {
        if (
          !baseMessages.some(
            (msg) =>
              msg.text === sentMsg.text &&
              msg.create_time === sentMsg.create_time
          )
        ) {
          baseMessages.push(sentMsg);
        }
      }

      setLocalMessages(baseMessages);

      if (hasTakenOver) {
        setIsThinking(false);
      }
    }
  }, [isOpen, transcript, sentMessages, hasTakenOver]);

  useEffect(() => {
    if (!isOpen) return;

    const currentMsgs = [...localMessages];

    if (wsMessages.length > 0) {
      for (const msg of wsMessages) {
        const speaker = msg?.speaker?.toLowerCase();
        if (speaker === "customer" && !hasTakenOver) {
          setIsThinking(true);
        }

        if (speaker === "agent") {
          setIsThinking(false);
        }

        if (
          !currentMsgs.some(
            (m) => m.text === msg.text && m.create_time === msg.create_time
          )
        ) {
          currentMsgs.push(msg);
        }
      }
    }

    if (messages.length > 0) {
      for (const msg of messages) {
        if (
          !currentMsgs.some(
            (m) => m.text === msg.text && m.create_time === msg.create_time
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
            m.text === sentMsg.text && m.create_time === sentMsg.create_time
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
        create_time: now.toString(),
        type: "takeover",
      } as TranscriptEntry);
    }

    setLocalMessages(currentMsgs);

    if (!userInitiatedTakeOver) {
      setHasTakenOver(
        transcript?.status === "takeover" ||
          currentMsgs.some((msg) => msg.type === "takeover")
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsMessages, messages, sentMessages, isOpen, userInitiatedTakeOver]);

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
  const in_progress_hostility_score = currentHostility ?? 0;
  const liveTopic =
    typeof statistics?.topic === "string" && statistics.topic.trim() !== ""
      ? statistics.topic
      : undefined;
  const topicText =
    liveTopic ||
    conversationStats.topic ||
    transcript.metadata?.topic ||
    "Active Conversation";

  const handleTakeOver = async () => {
    if (!transcript?.id) return;
    setLoading(true);
    try {
      const success = onTakeOver
        ? await onTakeOver(transcript.id)
        : await conversationService.takeoverConversation(transcript.id);

      if (success) {
        setHasTakenOver(true);
        setIsThinking(false);
        setUserInitiatedTakeOver(true);

        // Preserve any locally submitted feedback when takeover triggers a refresh
        try {
          if (userFeedback) {
            if (Array.isArray(transcript.feedback)) {
              const exists = transcript.feedback.some(
                (f) =>
                  f.feedback_message === userFeedback.feedback_message &&
                  f.feedback_timestamp === userFeedback.feedback_timestamp
              );
              if (!exists)
                transcript.feedback = [...transcript.feedback, userFeedback];
            } else {
              transcript.feedback = [userFeedback];
            }
          }
        } catch {}

        const now = Date.now();
        const conversationCreateTime = transcript.create_time
          ? new Date(transcript.create_time).getTime()
          : now;
        const takeoverEntry: TranscriptEntry = {
          speaker: "",
          text: "",
          start_time: (now - conversationCreateTime) / 1000,
          end_time: (now - conversationCreateTime) / 1000,
          create_time: now.toString(),
          type: "takeover",
        };

        setLocalMessages((prev) => [...prev, takeoverEntry]);

        if (refetchConversations) {
          refetchConversations();
        }
      } else {
      }
    } catch (error) {
    } finally {
      setLoading(false);
    }
  };

  const durationInSeconds =
    conversationStats.duration > 3600 * 24
      ? Math.floor(conversationStats.duration / 1000)
      : conversationStats.duration;

  const handleSendMessage = async () => {
    if (!chatInput.trim() || !transcript?.id) return;

    const now = Date.now();
    const conversationCreateTime = transcript.create_time
      ? new Date(transcript.create_time).getTime()
      : now;
    const newEntry: TranscriptEntry = {
      speaker: "agent",
      text: chatInput.trim(),
      start_time: (now - conversationCreateTime) / 1000,
      end_time: (now - conversationCreateTime) / 1000 + 0.01,
      create_time: now,
    };

    setChatInput("");

    try {
      await conversationService.updateConversation(transcript.id, {
        messages: [newEntry],
        llm_analyst_id: DEFAULT_LLM_ANALYST_ID,
      });

      if (refetchConversations) refetchConversations();
    } catch (err) {
      // ignore
    }
  };

  const handleFinalize = async () => {
    if (!transcript?.id) return;

    setIsFinalizing(true);

    const processingToast = toast.loading("Processing conversation...", {
      duration: Infinity,
    });

    try {
      await conversationService.finalizeConversation(transcript.id);
      toast.dismiss(processingToast);
      toast.success("Conversation finalized successfully.");

      if (refetchConversations) refetchConversations();
      onOpenChange(false);
    } catch (err) {
      toast.dismiss(processingToast);
      toast.error("Failed to finalize conversation.");
    } finally {
      setIsFinalizing(false);
    }
  };

  const handleFeedbackSubmit = async () => {
    if (!transcript?.id || !feedbackType || !feedbackMessage.trim()) {
      toast.error("Please select rating and enter a message.");
      return;
    }
    setFeedbackSubmitting(true);
    try {
      const ok = await submitConversationFeedback(
        transcript.id,
        feedbackType,
        feedbackMessage.trim()
      );
      if (ok) {
        const newFeedback: ConversationFeedbackEntry = {
          feedback: feedbackType,
          feedback_message: feedbackMessage.trim(),
          feedback_timestamp: new Date().toISOString(),
          feedback_user_id: "current-user",
        };
        setUserFeedback(newFeedback);
        try {
          if (Array.isArray(transcript.feedback)) {
            transcript.feedback = [...transcript.feedback, newFeedback];
          } else {
            transcript.feedback = [newFeedback];
          }
          feedbackCacheRef.current.set(transcript.id, newFeedback);
        } catch {}
        setFeedbackType(null);
        setFeedbackMessage("");
        toast.success("Feedback submitted successfully.");
      } else {
        toast.error("Failed to submit feedback.");
      }
    } catch (e) {
      toast.error("Failed to submit feedback.");
    } finally {
      setFeedbackSubmitting(false);
    }
  };

  return (
    <>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5" />
          <span>Chat #{transcript.id.slice(-4)}</span>
          <Badge
            variant="default"
            className={`ml-2 ${
              sentiment === "positive"
                ? "bg-green-600 text-white"
                : sentiment === "negative"
                ? "bg-red-600 text-white"
                : "bg-purple-600 text-white"
            }`}
          >
            {sentiment.charAt(0).toUpperCase() + sentiment.slice(1)}
          </Badge>
          {isConnected && (
            <Badge
              variant="outline"
              className="ml-2 bg-green-50 text-green-700 border-green-200"
            >
              Live
            </Badge>
          )}
          {hasTakenOver && (
            <Badge
              variant="outline"
              className="ml-2 bg-blue-50 text-blue-700 border-blue-200"
            >
              Supervisor Mode
            </Badge>
          )}
        </DialogTitle>
      </DialogHeader>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:h-[550px] md:overflow-hidden">
        <div className="space-y-4 flex flex-col h-full">
          <Tabs
            value={leftPanelTab}
            onValueChange={(v) => setLeftPanelTab(v as "stats" | "feedback")}
            className="w-full"
          >
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="stats">Stats</TabsTrigger>
              <TabsTrigger value="feedback">Feedback</TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="flex-1 overflow-y-auto">
            {leftPanelTab === "feedback" ? (
              <div className="space-y-4">
                {userFeedback ? (
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-sm font-medium mb-3">Rate</h4>
                      <div className="flex items-center gap-2">
                        {userFeedback.feedback === "good" ? (
                          <>
                            <ThumbsUp className="w-5 h-5 text-green-600" />
                            <span className="text-sm font-medium text-green-600">
                              Good
                            </span>
                          </>
                        ) : (
                          <>
                            <ThumbsDown className="w-5 h-5 text-red-600" />
                            <span className="text-sm font-medium text-red-600">
                              Bad
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium mb-2">
                        Feedback for this message
                      </h4>
                      <p className="text-xs text-gray-500 mb-2">
                        {new Date(
                          userFeedback.feedback_timestamp
                        ).toLocaleString()}
                      </p>
                      <p className="text-sm text-gray-700 leading-relaxed">
                        {userFeedback.feedback_message}
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      className="w-full text-sm flex items-center gap-2"
                      onClick={() => {
                        setFeedbackType(userFeedback.feedback);
                        setFeedbackMessage(userFeedback.feedback_message);
                        setUserFeedback(null);
                      }}
                    >
                      <Pencil className="w-4 h-4" />
                      Edit Feedback
                    </Button>
                  </div>
                ) : (
                  <>
                    <div>
                      <h4 className="text-sm font-medium mb-3">Rate</h4>
                      <div className="flex gap-3">
                        <button
                          onClick={() => setFeedbackType("good")}
                          className={`p-2 rounded ${
                            feedbackType === "good"
                              ? "bg-green-100 text-green-600"
                              : "bg-gray-100 text-gray-400 hover:text-gray-600"
                          }`}
                        >
                          <ThumbsUp className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => setFeedbackType("bad")}
                          className={`p-2 rounded ${
                            feedbackType === "bad"
                              ? "bg-red-100 text-red-600"
                              : "bg-gray-100 text-gray-400 hover:text-gray-600"
                          }`}
                        >
                          <ThumbsDown className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium mb-3">
                        Feedback details
                      </h4>
                      <Textarea
                        rows={5}
                        value={feedbackMessage}
                        onChange={(e) => setFeedbackMessage(e.target.value)}
                        placeholder="Enter feedback details"
                        className="resize-none text-sm"
                      />
                    </div>
                    <Button
                      onClick={handleFeedbackSubmit}
                      disabled={
                        !feedbackType ||
                        !feedbackMessage.trim() ||
                        feedbackSubmitting
                      }
                      className="w-full bg-blue-600 text-white hover:bg-blue-700"
                    >
                      {feedbackSubmitting ? "Submitting..." : "Save"}
                    </Button>
                  </>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                <InfoBox
                  icon={<Timer />}
                  label="Duration"
                  value={formatDuration(durationInSeconds)}
                />
                <InfoBox
                  icon={<User />}
                  label="Agent/Customer Ratio"
                  value={`${conversationStats.agent_ratio || 0}% / ${
                    conversationStats.customer_ratio || 0
                  }%`}
                />
                <InfoBox
                  icon={<MessageCircle />}
                  label="Word Count"
                  value={`${conversationStats.word_count || 0}`}
                />
                <InfoBox
                  icon={<Frown />}
                  label="Hostility"
                  value={`${in_progress_hostility_score}%`}
                />

                <TopicBox
                  text={
                    hasTakenOver
                      ? "You have taken over this conversation"
                      : topicText
                  }
                />
              </div>
            )}
          </div>
        </div>

        <div className="md:col-span-2 flex flex-col h-full min-h-0">
          <div
            ref={scrollRef}
            className="flex-1 flex flex-col bg-secondary/30 rounded-lg p-3 overflow-y-auto min-h-0"
          >
            {localMessages.length > 0 ? (
              <div className="space-y-2">
                {localMessages.map((entry, idx) => {
                  if (entry.type === "takeover") {
                    return (
                      <div
                        className="flex justify-center my-3"
                        key={`takeover-${idx}-${entry.create_time}`}
                      >
                        <div className="px-3 py-1.5 rounded-full bg-blue-100 text-blue-800 text-xs font-medium flex items-center">
                          <User className="w-3 h-3 mr-1" />
                          Supervisor took over
                        </div>
                      </div>
                    );
                  }

                  const speaker = (entry.speaker || "").toLowerCase();
                  const isAdmin = speaker.includes("admin");
                  const isAgent =
                    speaker.includes("agent") || speaker.includes("operator");
                  const isCustomer =
                    speaker.includes("customer") || (!isAdmin && !isAgent);
                  const speakerName = isAdmin
                    ? "Admin"
                    : isAgent
                    ? "Agent"
                    : isCustomer
                    ? "Customer"
                    : "Unknown";
                  if (!entry.text || !entry.text.trim()) return null;

                  return (
                    <div
                      key={`${transcript.id}-message-${idx}-${entry.create_time}`}
                      className="message-container"
                    >
                      <div
                        className={`flex flex-col ${
                          isAgent ? "items-end" : "items-start"
                        }`}
                      >
                        <span className="text-[11px] text-black font-medium mb-1">
                          {speakerName}
                        </span>
                        <div
                          className={`p-2 rounded-lg max-w-[75%] sm:max-w-[90%] leading-tight break-words ${
                            isAgent
                              ? "bg-black text-white rounded-tl-lg"
                              : "bg-gray-200 text-gray-900 rounded-tr-lg"
                          }`}
                        >
                          <ConversationEntryWrapper entry={entry} />
                          <span className="block text-[10px] text-muted-foreground text-right mt-1">
                            {formatMessageTime(entry.create_time)}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
                {isThinking && !hasTakenOver && (
                  <div className="flex flex-col items-end">
                    <span className="text-[11px] text-black font-medium mb-1">
                      Agent
                    </span>
                    <div className="p-3 rounded-lg max-w-[75%] sm:max-w-[90%] leading-tight break-words bg-black text-white rounded-tl-lg">
                      <div className="flex items-center space-x-1">
                        <div
                          className="w-2 h-2 rounded-full bg-white/60 animate-bounce"
                          style={{ animationDelay: "0ms" }}
                        ></div>
                        <div
                          className="w-2 h-2 rounded-full bg-white/60 animate-bounce"
                          style={{ animationDelay: "150ms" }}
                        ></div>
                        <div
                          className="w-2 h-2 rounded-full bg-white/60 animate-bounce"
                          style={{ animationDelay: "300ms" }}
                        ></div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center text-muted-foreground py-6">
                No messages yet.
              </div>
            )}
          </div>

          <div className="mt-4 space-y-3">
            {!hasTakenOver ? (
              <Button
                onClick={handleTakeOver}
                className="w-full bg-black text-white"
                disabled={
                  loading || transcript.status === "complete" || hasTakenOver
                }
              >
                {loading ? "Processing..." : "Take Over Conversation"}
              </Button>
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <Input
                    className="flex-1"
                    placeholder="Type a message as Admin..."
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                  />
                  <Button
                    onClick={handleSendMessage}
                    className="px-4 py-2 bg-black text-white"
                  >
                    Send
                  </Button>
                </div>
                <Button
                  onClick={handleFinalize}
                  className="bg-red-600 text-white w-full"
                  disabled={isFinalizing}
                >
                  {isFinalizing ? "Finalizing..." : "Finalize Conversation"}
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function InfoBox({
  icon,
  label,
  value,
}: {
  icon: JSX.Element;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center p-3 bg-primary/5 rounded-lg">
      {icon}
      <span className="text-sm font-medium">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

function TopicBox({ text }: { text: string }) {
  return (
    <div className="flex bg-amber-50 rounded-xl p-4">
      <AlertTriangle className="w-5 h-5 text-amber-600 mt-1" />
      <div className="flex flex-col justify-start items-start ml-3">
        <span className="text-sm font-semibold leading-tight">Topic</span>
        <span className="text-sm">{text}</span>
      </div>
    </div>
  );
}
