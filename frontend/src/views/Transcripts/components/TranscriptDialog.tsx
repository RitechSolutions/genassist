import {
  PlayCircle,
  Timer,
  MessageCircle,
  Volume2,
  TrendingUp,
  ThumbsUp,
  BotMessageSquare,
  MessageSquare,
  CheckCircle,
  Timer as TimerIcon,
  Clock,
  User,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { useEffect, useRef, useState } from "react";
import { getAudioUrl } from "@/services/transcripts";
import { Transcript } from "@/interfaces/transcript.interface";
import { Input } from "@/components/input";
import { Button } from "@/components/button";
import { askAIQuestion } from "@/services/aiChat";
import { Tabs, TabsList, TabsTrigger } from "@/components/tabs";
import { formatMessageTime, formatCallTimestamp, formatDuration } from "../helpers/formatting";

type TranscriptDialogProps = {
  transcript: Transcript | null;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
};

const isCallTranscript = (transcript: Transcript | null) => {
  if (!transcript) return false;
  return Boolean(transcript.recording_id) || Boolean(transcript.metadata?.isCall);
};

export function TranscriptDialog({
  transcript,
  isOpen,
  onOpenChange,
}: TranscriptDialogProps) {
  const [audioSrc, setAudioSrc] = useState<string>("");
  const [chatInput, setChatInput] = useState<string>("");
  const [aiMessagesByTranscript, setAiMessagesByTranscript] = useState<{
    [key: string]: { role: string; text: string }[];
  }>({});
  const [activeTab, setActiveTab] = useState<"transcript" | "ai">("transcript");
  const [loading, setLoading] = useState(false);
  const [audioLoading, setAudioLoading] = useState(false);

  const chatContainerRef = useRef<HTMLDivElement>(null);
  const isCall = isCallTranscript(transcript);

  useEffect(() => {
    if (transcript && isCall) {
      setAudioLoading(true);
      getAudioUrl(transcript.id).then((url) => {
        setAudioSrc(url);
        setAudioLoading(false);
      }).catch(() => {
        setAudioLoading(false);
      });
    } else {
      setAudioSrc("");
    }
  }, [transcript, isCall]);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop =
        chatContainerRef.current.scrollHeight;
    }
  }, [aiMessagesByTranscript]);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop =
        chatContainerRef.current.scrollHeight;
    }
  }, [aiMessagesByTranscript]);

  const handleSendMessage = async () => {
    if (chatInput.trim() === "" || !transcript) return;

    const userMessage = { role: "Me", text: chatInput };

    setAiMessagesByTranscript((prev) => ({
      ...prev,
      [transcript.id]: [...(prev[transcript.id] || []), userMessage],
    }));

    setChatInput("");
    setActiveTab("ai");
    setLoading(true);

    try {
      const response = await askAIQuestion(transcript.id, chatInput);
      const aiResponse = { role: "GenAssist AI", text: response.answer };

      setAiMessagesByTranscript((prev) => ({
        ...prev,
        [transcript.id]: [...(prev[transcript.id] || []), aiResponse],
      }));
    } catch (error) {
      setAiMessagesByTranscript((prev) => ({
        ...prev,
        [transcript.id]: [
          ...(prev[transcript.id] || []),
          {
            role: "GenAssist AI",
            text: "Sorry, I couldn't process your request at the moment.",
          },
        ],
      }));
    } finally {
      setLoading(false);
    }
  };

  if (!transcript) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {isCall ? (
              <PlayCircle className="w-5 h-5" />
            ) : (
              <MessageSquare className="w-5 h-5" />
            )}
            {isCall ? "Call" : "Chat"} #{(transcript?.metadata?.title ?? "----").slice(0, 4)}{" "}
          </DialogTitle>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
          <div className="space-y-4 flex flex-col">
            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col items-center p-3 bg-primary/5 rounded-lg">
                <Timer className="w-5 h-5 mb-1 text-primary" />
                <span className="text-sm font-medium">
                {formatDuration(Number(transcript.duration))}
                </span>
                <span className="text-xs text-muted-foreground">Duration</span>
              </div>
              <div className="flex flex-col items-center p-3 bg-primary/5 rounded-lg">
                <MessageCircle className="w-5 h-5 mb-1 text-primary" />
                <span className="text-sm font-medium">
                  {transcript.metrics.wordCount}
                </span>
                <span className="text-xs text-muted-foreground">Words</span>
              </div>
              <div className="flex flex-col items-center p-3 bg-primary/5 rounded-lg">
                <Volume2 className="w-5 h-5 mb-1 text-primary" />
                <span className="px-2 py-0.5 text-xs font-normal rounded-full bg-yellow-100 text-orange-600 mb-1 capitalize">
                  {transcript.metrics.sentiment}
                </span>
                <span className="text-xs text-muted-foreground">Sentiment</span>
              </div>

              <div className="flex flex-col items-center p-3 bg-primary/5 rounded-lg">
                <TrendingUp className="w-5 h-5 mb-1 text-primary" />
                <span className="text-sm font-medium">
                  {transcript.metrics.speakingRatio.agent}% /{" "}
                  {transcript.metrics.speakingRatio.customer}%
                </span>
                <span className="text-xs text-muted-foreground">
                  Operator/Customer Ratio
                </span>
              </div>
              
            </div>

            <div className="p-3 rounded-lg">
              <h4 className="text-sm font-medium mb-2">Conversation Tone</h4>
              <div className="flex flex-wrap gap-2">
                {transcript.metrics.tone.map((tone, index) => (
                  <span
                    key={index}
                    className="px-2 py-1 bg-gray-100 text-gray-900 rounded-full text-xs font-bold"
                  >
                    {tone.toLowerCase()}
                  </span>
                ))}
              </div>
            </div>

            {isCall && (
              <div className="bg-primary/5 p-4 rounded-lg">
                {audioLoading ? (
                  <div className="animate-pulse">
                    <div className="h-14 bg-gray-300 rounded-md w-full"></div>
                  </div>
                ) : audioSrc ? (
                  <audio controls className="w-full [&::-webkit-media-controls-panel]:bg-white [&::-webkit-media-controls-panel]:text-black">
                    <source src={audioSrc} type="audio/mpeg"/>
                    Your browser does not support the audio element.
                  </audio>
                ) : (
                  <div className="text-center text-sm text-muted-foreground py-2">
                    No audio available for this call
                  </div>
                )}
              </div>
            )}
            <div className="flex flex-col gap-4">
              <div className="flex bg-gray-100 rounded-xl p-6">
                <ThumbsUp className="w-5 h-5 text-green-600 mt-1" />
                <div className="flex flex-col justify-start items-start ml-3">
                  <span className="text-sm font-semibold leading-tight">{transcript.metrics.customerSatisfaction > 0 
                            ? `${Math.round((transcript.metrics.customerSatisfaction / 10) * 100)}%` 
                            : "0%"}</span>
                  <span className="text-sm">Satisfaction</span>
                </div>
              </div>

              <div className="flex bg-gray-100 rounded-xl p-4">
                <Clock className="w-5 h-5 text-purple-600 mt-1" />
                <div className="flex flex-col justify-start items-start ml-3">
                  <span className="text-sm font-semibold leading-tight">{transcript.metrics.serviceQuality > 0 
                            ? `${Math.round((transcript.metrics.serviceQuality / 10) * 100)}%` 
                            : "0%"}</span>
                  <span className="text-sm">Service Quality</span>
                </div>
              </div>

              <div className="flex bg-gray-100 rounded-xl p-4">
                <CheckCircle className="w-5 h-5 text-red-600 mt-1" />
                <div className="flex flex-col justify-start items-start ml-3">
                  <span className="text-sm font-semibold leading-tight">{transcript.metrics.serviceQuality > 0 
                            ? `${Math.round((transcript.metrics.resolutionRate / 10) * 100)}%` 
                            : "0%"}</span>
                  <span className="text-sm">Resolution Rate</span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-col">
            <Tabs
              value={activeTab}
              onValueChange={(value) =>
                setActiveTab(value as "transcript" | "ai")
              }
              className="pb-1"
            >
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="transcript">Transcript</TabsTrigger>
                <TabsTrigger value="ai">Chat</TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="flex-1 flex flex-col bg-secondary/30 rounded-lg overflow-hidden">
              {activeTab === "transcript" ? (
                <div className="p-3 overflow-y-auto text-[13px] sm:text-[12px]" style={{height: isCall ? "550px" : "450px"}}>
                  <div className="space-y-2">
                    {transcript.transcript?.map((entry, index) => {
                      
                      const entryObj = typeof entry === 'string' ? JSON.parse(entry) : entry;
                      const entryType = entryObj.type || '';
                      
                      if (entryType === "takeover" || 
                          (entryObj.speaker === "Unknown" && entryObj.text === "" && entryObj.start_time === 0)) {
                        return (
                          <div className="flex justify-center my-3" key={`takeover-${index}-${entryObj.create_time || index}`}>
                            <div className="px-3 py-1.5 rounded-full bg-blue-100 text-blue-800 text-xs font-medium flex items-center">
                              <User className="w-3 h-3 mr-1" />
                              Supervisor took over
                            </div>
                          </div>
                        );
                      }

                      // Skip empty messages
                      if ((entryObj.text === "" || !entryObj.text) && (entryObj.speaker === "" || !entryObj.speaker)) {
                        return null;
                      }

                      const isAgent = ["Agent", "agent"].includes(
                        entryObj.speaker
                      );
                      const speakerName = isAgent ? "Operator" : "Customer";

                      return (
                        <div
                          key={index}
                          className={`flex flex-col ${isAgent ? "items-end" : "items-start"}`}
                        >
                          <span className="text-[11px] text-black font-medium mb-1">
                          {speakerName}
                        </span>
                          <div
                            className={`p-2 rounded-lg max-w-[75%] sm:max-w-[90%] leading-tight break-words ${
                              isAgent
                                ? "bg-black text-white rounded-tl-lg rounded-tr-none"
                                : "bg-gray-200 text-gray-900 rounded-tr-lg rounded-tl-none"
                            }`}
                          >
                            
                            {entryObj.text}
                            <span className="block text-[10px] text-muted-foreground text-right mt-1">
                              {isCall 
                                ? formatCallTimestamp(entryObj.start_time)
                                : formatMessageTime(entryObj.create_time)
                              }
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div
                  ref={chatContainerRef}
                  className="p-3 overflow-y-auto text-[13px] sm:text-[12px]" style={{height: isCall ? "550px" : "450px"}}
                >
                  {aiMessagesByTranscript[transcript.id]?.length > 0 ? (
                    <div className="space-y-2">
                      {aiMessagesByTranscript[transcript.id]?.map(
                        (msg, index) => (
                          <div
                            key={index}
                            className={`flex ${
                              msg.role === "Me"
                                ? "justify-end"
                                : "justify-start"
                            }`}
                          >
                            <div
                              className={`p-2 rounded-lg max-w-[75%] sm:max-w-[90%] leading-tight break-words ${
                                msg.role === "Me"
                                  ? "bg-blue-100 text-blue-900"
                                  : "bg-green-100 text-green-900"
                              }`}
                            >
                              <span className="block text-[11px] text-muted-foreground font-medium">
                                {msg.role}
                              </span>
                              {msg.text}
                            </div>
                          </div>
                        )
                      )}
                      {loading && (
                        <div className="flex justify-start">
                          <div className="p-2 rounded-lg bg-gray-100 text-gray-900 max-w-[75%]">
                            <span className="block text-[11px] text-muted-foreground font-medium">
                              GenAssist AI
                            </span>
                            Thinking...
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="flex flex-1 flex-col justify-center items-center text-muted-foreground">
                      <BotMessageSquare className="w-12 h-12 text-gray-400" />
                      <p className="text-sm mt-2">What can I help with?</p>
                    </div>
                  )}
                </div>
              )}

            </div>
            <div className="mt-2 flex items-center gap-2 bg-secondary/30 p-2 rounded-lg">
              <Input
                className="flex-1"
                type="text"
                placeholder="Ask GenAI"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
              />
              <Button onClick={handleSendMessage} className="px-4 py-2 bg-black text-white">
                Send
              </Button>
            </div>
          </div>
        </div>

      </DialogContent>
    </Dialog>
  );
}