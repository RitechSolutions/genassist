import {
  Timer,
  MessageSquare,
  AlertTriangle,
  User,
  Frown,
  MessageCircle,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Transcript, TranscriptEntry } from "@/interfaces/transcript.interface";
import { Input } from "@/components/input";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { conversationService } from "@/services/liveConversations";
import { useWebSocketTranscript } from "../hooks/useWebsocket";
import { PRIVATE_WS, PUBLIC_WS, getApiUrl } from "@/config/api";
import { DEFAULT_LLM_ANALYST_ID } from "@/constants/llmModels";
import toast from "react-hot-toast";
import { formatDuration, formatMessageTime } from "../helpers/format";

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
}

const getStoredConversationStats = (
  conversationId: string
): ConversationStats | null => {
  try {
    const savedStats = localStorage.getItem(
      `conversation_stats_${conversationId}`
    );
    if (!savedStats) return null;

    const parsedStats = JSON.parse(savedStats);

    if (parsedStats.duration !== undefined) {
      parsedStats.duration = Number(parsedStats.duration);
    }

    return parsedStats;
  } catch (e) {
    console.error("Error reading conversation stats from localStorage", e);
    return null;
  }
};

const saveConversationStats = (
  conversationId: string,
  stats: ConversationStats
): void => {
  try {
    const cleanedStats = {
      ...stats,
      duration: stats.duration !== undefined ? Number(stats.duration) : 0,
      agent_ratio:
        stats.agent_ratio !== undefined ? Number(stats.agent_ratio) : 0,
      customer_ratio:
        stats.customer_ratio !== undefined ? Number(stats.customer_ratio) : 0,
    };

    localStorage.setItem(
      `conversation_stats_${conversationId}`,
      JSON.stringify(cleanedStats)
    );
    console.log(`Saved stats for ${conversationId}:`, cleanedStats);
  } catch (e) {
    console.error("Error saving conversation stats to localStorage", e);
  }
};

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
  refetchConversations,
  messages = [],
}: Props): JSX.Element {
  const hasSupervisorTakeover = useMemo(() => {
    return transcript?.transcript?.some(entry => entry.type === "takeover") || false;
  }, [transcript?.transcript]);
  const storedStats = useMemo(() => {
    if (!transcript?.id) return null;
    return getStoredConversationStats(transcript.id);
  }, [transcript?.id]);

  const [hasTakenOver, setHasTakenOver] = useState(hasSupervisorTakeover);
  const [userInitiatedTakeOver, setUserInitiatedTakeOver] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [localMessages, setLocalMessages] = useState<TranscriptEntry[]>(
    transcript?.transcript || []
  );
  const [sentMessages, setSentMessages] = useState<TranscriptEntry[]>([]);
  const [isThinking, setIsThinking] = useState(false);

  const [conversationStats, setConversationStats] = useState<ConversationStats>(
    {
      agent_ratio: storedStats?.agent_ratio ?? transcript?.agent_ratio ?? 0,
      customer_ratio:
        storedStats?.customer_ratio ?? transcript?.customer_ratio ?? 0,
      duration:
        storedStats?.duration && storedStats.duration > 0
          ? storedStats.duration
          : transcript?.duration && transcript.duration > 0
          ? transcript.duration
          : 0,
      in_progress_hostility_score:
        storedStats?.in_progress_hostility_score ??
        transcript?.in_progress_hostility_score ??
        0,
      word_count: storedStats?.word_count ?? transcript?.word_count ?? 0,
    }
  );

  const scrollRef = useRef<HTMLDivElement>(null);
  const [wsBaseUrl, setWsBaseUrl] = useState("");
  const [wsPort, setWsPort] = useState("");

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

  useEffect(() => {
    const testPrivateHost = async () => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 1000); // Fail after 1s

      try {
        await fetch(
          `https://${PRIVATE_WS.host}:${PRIVATE_WS.port}/api/health`,
          {
            signal: controller.signal,
            method: "GET",
            mode: "cors",
          }
        );
        setWsBaseUrl(PRIVATE_WS.host);
        setWsPort(PRIVATE_WS.port);
      } catch (err) {
        console.warn("Private WebSocket host not reachable, using public");
        setWsBaseUrl(PUBLIC_WS.host);
        setWsPort(PUBLIC_WS.port);
      } finally {
        clearTimeout(timeout);
      }
    };

    testPrivateHost();
  }, []);

  const shouldInitWebSocket =
    transcript?.id && wsBaseUrl !== "" && wsPort !== "";

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
          baseUrl: wsBaseUrl,
          port: wsPort,
          transcriptInitial: transcript?.transcript || [],
        }
      : {
          conversationId: "",
          token: "",
          baseUrl: "",
          port: "",
          transcriptInitial: [],
        }
  );

  useEffect(() => {
    if (isOpen && transcript?.id) {
      const stored = getStoredConversationStats(transcript.id);

      if (stored?.duration && stored.duration > 0) {
        console.log(
          `Using stored duration from localStorage: ${stored.duration}`
        );

        setConversationStats((prev) => ({
          ...prev,
          duration: Number(stored.duration),
          agent_ratio: stored.agent_ratio ?? prev.agent_ratio,
          customer_ratio: stored.customer_ratio ?? prev.customer_ratio,
          in_progress_hostility_score:
            stored.in_progress_hostility_score ??
            prev.in_progress_hostility_score,
          word_count: stored.word_count ?? prev.word_count,
        }));
      } else if (transcript.duration && transcript.duration > 0) {
        console.log(
          `No valid stored duration, using transcript duration: ${transcript.duration}`
        );

        const statsToSave = {
          ...conversationStats,
          duration: Number(transcript.duration),
        };

        saveConversationStats(transcript.id, statsToSave);
        setConversationStats(statsToSave);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  useEffect(() => {
    if (transcript && transcript.id) {
      const stored = getStoredConversationStats(transcript.id);

      setConversationStats((prevStats) => {
        const newStats: ConversationStats = { ...prevStats };
        let hasUpdates = false;

        if (
          transcript.agent_ratio !== undefined &&
          (stored?.agent_ratio === undefined || prevStats.agent_ratio === 0)
        ) {
          newStats.agent_ratio = Number(transcript.agent_ratio);
          hasUpdates = true;
        }

        if (
          transcript.customer_ratio !== undefined &&
          (stored?.customer_ratio === undefined ||
            prevStats.customer_ratio === 0)
        ) {
          newStats.customer_ratio = Number(transcript.customer_ratio);
          hasUpdates = true;
        }

        if (stored?.duration && stored.duration > 0) {
          newStats.duration = Number(stored.duration);
          hasUpdates = true;
        } else if (
          transcript.duration &&
          transcript.duration > 0 &&
          prevStats.duration === 0
        ) {
          newStats.duration = Number(transcript.duration);
          hasUpdates = true;
        }

        if (
          transcript.in_progress_hostility_score !== undefined &&
          (stored?.in_progress_hostility_score === undefined ||
            prevStats.in_progress_hostility_score === 0)
        ) {
          newStats.in_progress_hostility_score = Number(
            transcript.in_progress_hostility_score
          );
          hasUpdates = true;
        }

        if (
          transcript.word_count !== undefined &&
          (stored?.word_count === undefined || prevStats.word_count === 0)
        ) {
          newStats.word_count = Number(transcript.word_count);
          hasUpdates = true;
        }

        if (hasUpdates) {
          saveConversationStats(transcript.id, newStats);
          return newStats;
        }

        return prevStats;
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    transcript?.id,
    transcript?.agent_ratio,
    transcript?.customer_ratio,
    transcript?.duration,
    transcript?.in_progress_hostility_score,
    transcript?.word_count,
  ]);

  useEffect(() => {
    if (statistics && transcript?.id) {
      setConversationStats((prevStats) => {
        const newStats = { ...prevStats };
        let hasUpdates = false;

        if (typeof statistics.agent_ratio === "number") {
          newStats.agent_ratio = Number(statistics.agent_ratio);
          hasUpdates = true;
        }

        if (typeof statistics.customer_ratio === "number") {
          newStats.customer_ratio = Number(statistics.customer_ratio);
          hasUpdates = true;
        }

        if (typeof statistics.duration === "number") {
          newStats.duration = Number(statistics.duration);
          hasUpdates = true;
        }

        if (typeof statistics.in_progress_hostility_score === "number") {
          newStats.in_progress_hostility_score = Number(
            statistics.in_progress_hostility_score
          );
          hasUpdates = true;
        }

        if (typeof statistics.word_count === "number") {
          newStats.word_count = Number(statistics.word_count);
          hasUpdates = true;
        }

        if (hasUpdates) {
          console.log("Updating stats with WebSocket data:", newStats);
          saveConversationStats(transcript.id, newStats);
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

  useEffect(() => {
    if (isOpen && transcript) {
      const baseMessages = [...(transcript.transcript || [])];

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

      // bubble animation off when supervisor has taken over
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

    setLocalMessages(currentMsgs);
    
    if (!userInitiatedTakeOver) {
      setHasTakenOver(currentMsgs.some(msg => msg.type === "takeover"));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsMessages, messages, sentMessages, isOpen, userInitiatedTakeOver]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [localMessages]);

  const sentiment = transcript.metrics?.sentiment || "neutral";
  const in_progress_hostility_score =
    conversationStats.in_progress_hostility_score ?? 0;
  const topicText = transcript.metadata?.topic || "Active Conversation";

  const handleTakeOver = async () => {
    if (!transcript?.id) return;
    setLoading(true);
    try {
      const success = await conversationService.takeoverConversation(
        transcript.id
      );
      if (success) {
        setHasTakenOver(true);
        setIsThinking(false);
        setUserInitiatedTakeOver(true);

        const now = Date.now();
        const takeoverEntry: TranscriptEntry = {
          speaker: "",
          text: "",
          start_time: 0,
          end_time: 0,
          create_time: now.toString(),
          type: "takeover"
        };
        
        setLocalMessages(prev => [...prev, takeoverEntry]);

        if (refetchConversations) {
          refetchConversations();
        }
      } else {
        console.error("Takeover failed");
      }
    } catch (error) {
      console.error("Failed to take over conversation:", error);
    } finally {
      setLoading(false);
    }
  };

  const durationInSeconds = conversationStats.duration > 3600 * 24
  ? Math.floor(conversationStats.duration / 1000)
  : conversationStats.duration;

  const handleSendMessage = async () => {
    if (!chatInput.trim() || !transcript?.id) return;

    const now = Date.now();
    const newEntry: TranscriptEntry = {
      speaker: "agent",
      text: chatInput.trim(),
      start_time: now / 1000,
      end_time: now / 1000 + 0.01,
      create_time: now,
    };

    // setLocalMessages((prev) => [...prev, newEntry]);
    // setSentMessages((prev) => [...prev, newEntry]);
    setChatInput("");

    try {
      await conversationService.updateConversation(transcript.id, {
        messages: [newEntry],
        llm_analyst_id: DEFAULT_LLM_ANALYST_ID,
      });

      // if (isConnected) {
      //   sendMessage(newEntry);
      // }

      if (refetchConversations) refetchConversations();
    } catch (err) {
      console.error("Failed to send message", err);
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
      toast.success("Conversation finalized successfully");

      if (refetchConversations) refetchConversations();
      onOpenChange(false);
    } catch (err) {
      toast.dismiss(processingToast);
      toast.error("Failed to finalize conversation");
      console.error("Finalize failed", err);
    } finally {
      setIsFinalizing(false);
    }
  };

  return (
    <>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5" />
          <span>Chat #{transcript.id.slice(-4)}</span>
          <Badge
            variant={
              sentiment === "positive"
                ? "default"
                : sentiment === "negative"
                ? "destructive"
                : "secondary"
            }
            className="ml-2"
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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
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
              hasTakenOver ? "You have taken over this conversation" : topicText
            }
          />
        </div>

        <div className="md:col-span-2 flex flex-col h-full">
          <div
            ref={scrollRef}
            className="flex-1 flex flex-col bg-secondary/30 rounded-lg p-3 overflow-y-auto max-h-[450px]"
          >
            {localMessages.length > 0 ? (
              <div className="space-y-2">
                {localMessages.map((entry, idx) => {
                  if (entry.type === "takeover") {
                    return (
                      <div className="flex justify-center my-3" key={`takeover-${idx}-${entry.create_time}`}>
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
                          {entry.text}
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

          {!hasTakenOver ? (
            <Button
              onClick={handleTakeOver}
              className="w-full bg-black text-white mt-4"
              disabled={loading || transcript.status === "complete"}
            >
              {loading ? "Processing..." : "Take Over Conversation"}
            </Button>
          ) : (
            <>
              <div className="mt-4 flex items-center gap-2">
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
                className="mt-4 bg-red-600 text-white w-full"
                disabled={isFinalizing}
              >
                {isFinalizing ? "Finalizing..." : "Finalize Conversation"}
              </Button>
            </>
          )}
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
