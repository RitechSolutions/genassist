import {
  PlayCircle,
  ThumbsUp,
  ThumbsDown,
  BotMessageSquare,
  MessageSquare,
  User,
  Pencil,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { useEffect, useRef, useState, useCallback } from "react";
import { getAudioUrl, submitConversationFeedback, submitMessageFeedback } from "@/services/transcripts";
import { Transcript, ConversationFeedbackEntry } from "@/interfaces/transcript.interface";
import { Input } from "@/components/input";
import { Button } from "@/components/button";
import { askAIQuestion } from "@/services/aiChat";
import { Tabs, TabsList, TabsTrigger } from "@/components/tabs";
import { Textarea } from "@/components/textarea";
import { useToast } from "@/hooks/useToast";
import { formatMessageTime, formatCallTimestamp, getEffectiveSentiment } from "../helpers/formatting";
import { MetricCards } from "./MetricCard";
import { ScoreCards } from "./ScoreCard";
import { TranscriptAudioPlayer } from "./TranscriptAudioPlayer";
import { MessageFeedbackPopover } from "./MessageFeedbackPopover";

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
  const [leftPanelTab, setLeftPanelTab] = useState<"stats" | "feedback">("stats");
  const [feedbackType, setFeedbackType] = useState<"good" | "bad" | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [userFeedback, setUserFeedback] = useState<ConversationFeedbackEntry | null>(null);
  const [localTranscript, setLocalTranscript] = useState<Transcript | null>(transcript);
  const [openPopoverMessageId, setOpenPopoverMessageId] = useState<string | null>(null);

  useEffect(() => {
    setLocalTranscript(transcript);
  }, [transcript]);

  const chatContainerRef = useRef<HTMLDivElement>(null);
  const isCall = isCallTranscript(localTranscript);
  const { toast } = useToast();

useEffect(() => {
  if (!localTranscript || !isCall) return;

  const recId = localTranscript.recording_id;
  if (!recId) {
    return;
  }

  setAudioLoading(true);
  getAudioUrl(recId)
    .then((blobUrl) => {
      setAudioSrc(blobUrl);
    })
    .catch((err) => {
      // ignore
    })
    .finally(() => {
      setAudioLoading(false);
    });
}, [localTranscript, isCall]);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop =
        chatContainerRef.current.scrollHeight;
    }
  }, [aiMessagesByTranscript]);

  // Check for existing user feedback when component loads
  useEffect(() => {
    if (localTranscript?.feedback && localTranscript.feedback.length > 0) {
      // Find the most recent feedback from the current user
      const latestUserFeedback = localTranscript.feedback[localTranscript.feedback.length - 1];
      setUserFeedback(latestUserFeedback);
    } else {
      // Reset feedback state if no feedback exists for this transcript
      setUserFeedback(null);
    }
    
    // Reset form state when switching transcripts
    setIsEditing(false);
    setFeedbackType(null);
    setFeedbackMessage("");
  }, [localTranscript]);

  // keep persisted feedback
  useEffect(() => {
    if (!isOpen) {
      setIsEditing(false);
      setFeedbackType(null);
      setFeedbackMessage("");
    }
  }, [isOpen]);

  // When dialog opens, hydrate from transcript if available
  const feedbackCount = Array.isArray(localTranscript?.feedback) ? localTranscript.feedback.length : 0;
  useEffect(() => {
    if (!isOpen) return;
    if (Array.isArray(localTranscript?.feedback) && localTranscript.feedback.length > 0) {
      setUserFeedback(localTranscript.feedback[localTranscript.feedback.length - 1]);
    }
  }, [isOpen, feedbackCount, localTranscript?.feedback]);

  const handleSendMessage = async () => {
    if (chatInput.trim() === "" || !localTranscript) return;

    const userMessage = { role: "Me", text: chatInput };

    setAiMessagesByTranscript((prev) => ({
      ...prev,
      [localTranscript.id]: [...(prev[localTranscript.id] || []), userMessage],
    }));

    setChatInput("");
    setActiveTab("ai");
    setLoading(true);

    try {
      const response = await askAIQuestion(localTranscript.id, chatInput);
      const aiResponse = { role: "GenAssist AI", text: response.answer };

      setAiMessagesByTranscript((prev) => ({
        ...prev,
        [localTranscript.id]: [...(prev[localTranscript.id] || []), aiResponse],
      }));
    } catch (error) {
      setAiMessagesByTranscript((prev) => ({
        ...prev,
        [localTranscript.id]: [
          ...(prev[localTranscript.id] || []),
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

  const handleFeedbackSubmit = async () => {
    if (!localTranscript || !feedbackType || !feedbackMessage.trim()) {
      toast({
        title: "Error",
        description: "Please select feedback type and enter a message.",
        variant: "destructive",
      });
      return;
    }

    setFeedbackSubmitting(true);

    try {
      const success = await submitConversationFeedback(
        localTranscript.id,
        feedbackType,
        feedbackMessage.trim()
      );

      if (success) {
        const newFeedback = {
          feedback: feedbackType,
          feedback_message: feedbackMessage.trim(),
          feedback_timestamp: new Date().toISOString(),
          feedback_user_id: "", // set by the service
        };

        // update local state so the dialog reflects feedback immediately
        setUserFeedback(newFeedback);
        // push it into the transcript object so future openings reflect it
        try {
          if (localTranscript) {
            if (Array.isArray(localTranscript.feedback)) {
              localTranscript.feedback = [...localTranscript.feedback, newFeedback];
            } else {
              localTranscript.feedback = [newFeedback];
            }
          }
        } catch {
          // ignore local update failure
        }
        setIsEditing(false);
        setFeedbackType(null);
        setFeedbackMessage("");

        toast({
          title: "Success",
          description: "Feedback submitted successfully!",
        });
      } else {
        toast({
          title: "Error",
          description: "Failed to submit feedback. Please try again.",
          variant: "destructive",
        });
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to submit feedback. Please try again.",
        variant: "destructive",
      });
    } finally {
      setFeedbackSubmitting(false);
    }
  };

  const handleEditFeedback = () => {
    if (userFeedback) {
      setFeedbackType(userFeedback.feedback);
      setFeedbackMessage(userFeedback.feedback_message);
      setIsEditing(true);
    }
  };

  const formatFeedbackDate = (timestamp: string) => {
    const date = new Date(timestamp);
    const month = date.toLocaleDateString('en-US', { month: 'long' });
    const day = date.getDate();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${month} ${day}, ${hours}:${minutes}`;
  };

  const handleMessageFeedback = async (messageId: string, feedback: "good" | "bad") => {
    if (!localTranscript?.id) return;
    const success = await submitMessageFeedback(messageId, feedback);
    if (success) {
      setLocalTranscript(currentTranscript => {
        if (!currentTranscript) return null;
        const base = (currentTranscript.messages ?? currentTranscript.messages) || [];
        const newTranscriptEntries = base.map(entry => {
          if (entry.message_id === messageId) {
            const newFeedback: ConversationFeedbackEntry = {
              feedback,
              feedback_message: "",
              feedback_timestamp: new Date().toISOString(),
              feedback_user_id: "", 
            };
            const existingFeedback = Array.isArray(entry.feedback) ? entry.feedback : [];
            return { ...entry, feedback: [...existingFeedback, newFeedback] };
          }
          return entry;
        });
        return { ...currentTranscript, messages: newTranscriptEntries, transcript: newTranscriptEntries };
      });
    }
  };

  const MessageFeedbackButton = ({ messageId, onOpenChange }: { messageId: string; onOpenChange?: (open: boolean) => void }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [text, setText] = useState("");

    const handleOpenChange = (open: boolean) => {
      setIsOpen(open);
      onOpenChange?.(open);
      
      // When opening, populate the text with existing feedback
      if (open) {
        const collection = (localTranscript?.messages ?? localTranscript?.messages) || [];
        const message = collection.find(entry => entry.message_id === messageId);
        const feedbackArr = Array.isArray(message?.feedback) ? message?.feedback as ConversationFeedbackEntry[] : [];
        const lastFeedback = feedbackArr.length > 0 ? feedbackArr[feedbackArr.length - 1] : null;
        setText(lastFeedback?.feedback_message || "");
      }
    };

    // Check if this message already has a feedback message
    const message = (localTranscript?.messages ?? localTranscript?.messages)?.find(entry => entry.message_id === messageId);
    const feedbackArr = Array.isArray(message?.feedback) ? message?.feedback as ConversationFeedbackEntry[] : [];
    const lastFeedback = feedbackArr.length > 0 ? feedbackArr[feedbackArr.length - 1] : null;
    const hasFeedbackMessage = lastFeedback?.feedback_message && lastFeedback.feedback_message.trim().length > 0;

    const handleClose = () => {
      handleOpenChange(false);
      setText("");
    };

    const handleSave = async () => {
      if (!messageId || !localTranscript) return;

      const base = (localTranscript.messages ?? localTranscript.messages) || [];
      const message = base.find(entry => entry.message_id === messageId);
      if (!message) return;

      const existingFeedback = Array.isArray(message.feedback) && message.feedback.length > 0
          ? message.feedback[message.feedback.length - 1]
          : null;

      const feedbackType = existingFeedback ? existingFeedback.feedback : "good";
      const success = await submitMessageFeedback(messageId, feedbackType, text);

      if (success) {
          setLocalTranscript(currentTranscript => {
              if (!currentTranscript) return null;
              const base = (currentTranscript.messages ?? currentTranscript.messages) || [];
              const newTranscriptEntries = base.map(entry => {
                  if (entry.message_id === messageId) {
                      const newFeedbackEntry: ConversationFeedbackEntry = {
                          feedback: feedbackType,
                          feedback_message: text,
                          feedback_timestamp: new Date().toISOString(),
                          feedback_user_id: "",
                      };
                      const existingFeedbackArr = Array.isArray(entry.feedback) ? entry.feedback : [];
                      const otherFeedback = existingFeedbackArr.filter(f => f.feedback !== feedbackType);
                      return { ...entry, feedback: [...otherFeedback, newFeedbackEntry] };
                  }
                  return entry;
              });
              return { ...currentTranscript, messages: newTranscriptEntries, transcript: newTranscriptEntries };
          });

          toast({ title: "Success", description: "Feedback message saved." });
          handleClose();
      } else {
          toast({ title: "Error", description: "Failed to save feedback.", variant: "destructive" });
      }
    };

    return (
      <MessageFeedbackPopover
        isOpen={isOpen}
        hasFeedbackMessage={hasFeedbackMessage}
        text={text}
        onOpenChange={handleOpenChange}
        onTextChange={setText}
        onSave={handleSave}
        onCancel={handleClose}
      />
    );
  };

  if (!localTranscript) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {isCall ? (
              <PlayCircle className="w-5 h-5" />
            ) : (
              <MessageSquare className="w-5 h-5" />
            )}
            {isCall ? "Call" : "Chat"} #{(localTranscript?.metadata?.title ?? "----").slice(0, 4)}{" "}
          </DialogTitle>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-[350px_1fr] gap-6 items-start">
          <div className="space-y-4 flex flex-col">
            {/* Left Panel Toggle */}
            <Tabs
              value={leftPanelTab}
              onValueChange={(value) => setLeftPanelTab(value as "stats" | "feedback")}
              className="w-full"
            >
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="stats">Stats</TabsTrigger>
                <TabsTrigger value="feedback">Feedback</TabsTrigger>
              </TabsList>
            </Tabs>

            {leftPanelTab === "stats" ? (
              <>
            <MetricCards
              duration={Number(localTranscript.duration)}
              wordCount={localTranscript.metrics.wordCount}
              sentiment={getEffectiveSentiment(localTranscript)}
              speakingRatio={localTranscript.metrics.speakingRatio}
            />

            <div className="p-3 rounded-lg">
              <h4 className="text-sm font-medium mb-2">Conversation Tone</h4>
              <div className="flex flex-wrap gap-2">
                {localTranscript.metrics.tone.map((tone, index) => (
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
              <TranscriptAudioPlayer isLoading={audioLoading} audioSrc={audioSrc} />
            )}
            <ScoreCards metrics={localTranscript.metrics} />
              </>
            ) : (
              <div className="space-y-4">
                {userFeedback && !isEditing ? (
                  // Display saved feedback
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-sm font-medium mb-3">Rate</h4>
                      <div className="flex items-center gap-2">
                        {userFeedback.feedback === "good" ? (
                          <>
                            <ThumbsUp className="w-5 h-5 text-green-600" />
                            <span className="text-sm font-medium text-green-600">Good</span>
                          </>
                        ) : (
                          <>
                            <ThumbsDown className="w-5 h-5 text-red-600" />
                            <span className="text-sm font-medium text-red-600">Bad</span>
                          </>
                        )}
                      </div>
                    </div>

                    <div>
                      <h4 className="text-sm font-medium mb-2">Feedback for this message</h4>
                      <p className="text-xs text-gray-500 mb-2">
                        {formatFeedbackDate(userFeedback.feedback_timestamp)}
                      </p>
                      <p className="text-sm text-gray-700 leading-relaxed">
                        {userFeedback.feedback_message}
                      </p>
                    </div>

                    <Button
                      onClick={handleEditFeedback}
                      variant="outline"
                      className="w-full text-sm flex items-center gap-2"
                    >
                      <Pencil className="w-4 h-4" />
                      Edit Feedback
                    </Button>
                  </div>
                ) : (
                  // Input form for diting feedback
                  <>
                    <div>
                      <h4 className="text-sm font-medium mb-3">Rate</h4>
                      <div className="flex gap-3">
                        <button
                          onClick={() => setFeedbackType("good")}
                          className={`p-2 rounded transition-all ${
                            feedbackType === "good"
                              ? "bg-green-100 text-green-600"
                              : "bg-gray-100 text-gray-400 hover:text-gray-600"
                          }`}
                        >
                          <ThumbsUp className="w-4 h-4" />
                        </button>
                        
                        <button
                          onClick={() => setFeedbackType("bad")}
                          className={`p-2 rounded transition-all ${
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
                      <h4 className="text-sm font-medium mb-3">Feedback details</h4>
                      <Textarea
                        placeholder="Enter feedback details"
                        value={feedbackMessage}
                        onChange={(e) => setFeedbackMessage(e.target.value)}
                        rows={6}
                        className="resize-none text-sm"
                      />
                    </div>

                    <div className="flex gap-2">
                      <Button
                        onClick={handleFeedbackSubmit}
                        disabled={!feedbackType || !feedbackMessage.trim() || feedbackSubmitting}
                        className="flex-1 bg-blue-600 text-white hover:bg-blue-700"
                      >
                        {feedbackSubmitting ? "Submitting..." : "Save"}
                      </Button>
                      
                      {isEditing && (
                        <Button
                          onClick={() => {
                            setIsEditing(false);
                            setFeedbackType(null);
                            setFeedbackMessage("");
                          }}
                          variant="outline"
                          className="px-4"
                        >
                          Cancel
                        </Button>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
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
                <div className="p-3 overflow-y-auto text-[13px] sm:text-[12px]" style={{height: isCall ? "500px" : "400px"}}>
                  <div className="space-y-2">
                    {(localTranscript.messages ?? localTranscript.messages)?.map((entry, index) => {
                      
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

                      const isAgent = ["Agent", "agent"].includes(entryObj.speaker);
                      const messageId = entryObj.message_id as string | undefined;
                      const messageFeedbackArr = Array.isArray(entryObj.feedback) ? entryObj.feedback as ConversationFeedbackEntry[] : [];
                      const hasGood = messageFeedbackArr.some(f => f.feedback === "good");
                      const hasBad = messageFeedbackArr.some(f => f.feedback === "bad");
                      const speakerName = isAgent ? "Operator" : "Customer";

                      return (
                        <div
                          key={index}
                          className={`flex flex-col ${isAgent ? "items-end" : "items-start"} group relative`}
                        >
                          <span className="text-[11px] text-black font-medium mb-1">
                          {speakerName}
                        </span>
                          <div className="relative">
                            {isAgent && (
                              <>
                                {/* No feedback given. Show on hover. */}
                                {!hasGood && !hasBad && (
                                    <div className={`absolute -left-28 top-1/2 -translate-y-1/2 ${openPopoverMessageId === messageId ? 'flex' : 'hidden group-hover:flex'} items-center gap-2 z-10`}>
                                        <div className="flex items-center bg-white rounded-lg shadow-sm border border-gray-200">
                                            <button
                                                className="p-2 hover:bg-gray-100 rounded-l-lg"
                                                title="Good response"
                                                onClick={() => handleMessageFeedback(messageId, "good")}
                                            >
                                                <ThumbsUp className="w-4 h-4 text-yellow-500" />
                                            </button>
                                            <div className="h-4 w-px bg-gray-200" />
                                            <button
                                                className="p-2 hover:bg-gray-100 rounded-r-lg"
                                                title="Bad response"
                                                onClick={() => handleMessageFeedback(messageId, "bad")}
                                            >
                                                <ThumbsDown className="w-4 h-4 text-yellow-500" />
                                            </button>
                                        </div>
                                        {messageId && <MessageFeedbackButton messageId={messageId} onOpenChange={(open) => setOpenPopoverMessageId(open ? messageId : null)} />}
                                    </div>
                                )}

                                {/* Thumbs up or down selected. */}
                                {(hasGood || hasBad) && (
                                    <div className="absolute -left-20 top-1/2 -translate-y-1/2 flex items-center gap-2 z-10">
                                        {/* Show selected icon permanently */}
                                        {hasGood && (
                                            <div className="flex items-center bg-white rounded-lg shadow-sm border border-green-200 p-2">
                                                <ThumbsUp className="w-4 h-4 text-green-600" />
                                            </div>
                                        )}
                                        {hasBad && (
                                            <div className="flex items-center bg-white rounded-lg shadow-sm border border-red-200 p-2">
                                                <ThumbsDown className="w-4 h-4 text-red-600" />
                                            </div>
                                        )}
                                        {messageId && <MessageFeedbackButton messageId={messageId} onOpenChange={(open) => setOpenPopoverMessageId(open ? messageId : null)} />}
                                    </div>
                                )}
                              </>
                            )}
                            <div
                              className={`p-2 rounded-lg leading-tight break-words inline-block ${
                              isAgent
                                ? "bg-black text-white rounded-tl-lg rounded-tr-none"
                                : "bg-gray-200 text-gray-900 rounded-tr-lg rounded-tl-none"
                            }`}
                              style={{maxWidth: '400px'}}
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
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div
                  ref={chatContainerRef}
                  className="p-3 overflow-y-auto text-[13px] sm:text-[12px]" style={{height: isCall ? "500px" : "400px"}}
                >
                  {aiMessagesByTranscript[localTranscript.id]?.length > 0 ? (
                    <div className="space-y-2">
                      {aiMessagesByTranscript[localTranscript.id]?.map(
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
              <Button onClick={handleSendMessage} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white">
                Send
              </Button>
            </div>
          </div>
        </div>

      </DialogContent>
    </Dialog>
  );
}
