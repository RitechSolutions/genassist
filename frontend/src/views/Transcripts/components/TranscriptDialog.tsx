import {
  PlayCircle,
  ThumbsUp,
  ThumbsDown,
  BotMessageSquare,
  MessageSquare,
  Pencil,
  Coins,
  Megaphone,
  Share2,
  Check,
} from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/dialog';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  getAudioUrl,
  submitConversationFeedback,
  submitMessageFeedback,
  fetchAgentResponseLogsByConversation,
  type AgentResponseLogSummary,
} from '@/services/transcripts';
import { Transcript, ConversationFeedbackEntry } from '@/interfaces/transcript.interface';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/button';
import { askAIQuestion } from '@/services/aiChat';
import { Tabs, TabsList, TabsTrigger } from '@/components/tabs';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/useToast';
import { getEffectiveSentiment } from '../helpers/formatting';
import { MetricCards } from './MetricCard';
import { ScoreCards } from './ScoreCard';
import { TranscriptAudioPlayer } from './TranscriptAudioPlayer';
import { TranscriptThread } from './TranscriptThread';
import { AgentResponseLogDialog } from '@/components/AgentResponseLogDialog';
import { Switch } from '@/components/switch';
import { DollarSign } from 'lucide-react';
import { formatFeedbackDate } from '@/helpers/utils';
import { useAgentsList } from '@/views/Analytics/hooks/useAgentsList';
import { useFeatureFlagVisible } from '@/components/featureFlag';
import { FeatureFlags } from '@/config/featureFlags';

type TranscriptDialogProps = {
  transcript: Transcript | null;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  /** When the list is filtered to one agent, pass its name so the header can show it without extra metadata on the row. */
  agentName?: string;
};

function resolveAgentNameFromTranscript(
  transcript: Transcript,
  agentNameMap: Record<string, string>
): string | undefined {
  const attrs = transcript.custom_attributes;
  if (!attrs) return undefined;

  const entries = Object.entries(attrs);
  const valueForKey = (...candidates: string[]) => {
    for (const c of candidates) {
      const cl = c.toLowerCase();
      const hit = entries.find(([k]) => k.toLowerCase() === cl);
      const v = hit?.[1];
      if (typeof v === 'string' && v.trim()) return v.trim();
    }
    return undefined;
  };

  const fromNameKeys = valueForKey('agent_name', 'agentName', 'Agent Name', 'genassist_agent_name');
  if (fromNameKeys) return fromNameKeys;

  const idVal = valueForKey('agent_id', 'agentId', 'Agent ID', 'genassist_agent_id');
  if (idVal && agentNameMap[idVal]) return agentNameMap[idVal];

  return undefined;
}

function resolveSupervisorId(transcript: Transcript): string | undefined {
  const directSupervisorId = transcript.supervisor_id?.trim();
  if (directSupervisorId) return directSupervisorId;

  const attrs = transcript.custom_attributes;
  if (!attrs) return undefined;

  const entries = Object.entries(attrs);
  const valueForKey = (...candidates: string[]) => {
    for (const c of candidates) {
      const cl = c.toLowerCase();
      const hit = entries.find(([k]) => k.toLowerCase() === cl);
      const v = hit?.[1];
      if (typeof v === 'string' && v.trim()) return v.trim();
    }
    return undefined;
  };

  return valueForKey('supervisor_id', 'supervisorId', 'operator_id', 'operatorId');
}

function resolveSupervisorUsernameFromAttrs(transcript: Transcript): string | undefined {
  const attrs = transcript.custom_attributes;
  if (!attrs) return undefined;

  const entries = Object.entries(attrs);
  const valueForKey = (...candidates: string[]) => {
    for (const c of candidates) {
      const cl = c.toLowerCase();
      const hit = entries.find(([k]) => k.toLowerCase() === cl);
      const v = hit?.[1];
      if (typeof v === 'string' && v.trim()) return v.trim();
    }
    return undefined;
  };

  return valueForKey('supervisor_username', 'supervisor_user_name', 'operator_username', 'operator_user_name');
}

const isCallTranscript = (transcript: Transcript | null) => {
  if (!transcript) return false;
  return Boolean(transcript.recording_id) || Boolean(transcript.metadata?.isCall);
};

export function TranscriptDialog({ transcript, isOpen, onOpenChange, agentName: agentNameProp }: TranscriptDialogProps) {
  const [audioSrc, setAudioSrc] = useState<string>('');
  const [chatInput, setChatInput] = useState<string>('');
  const [aiMessagesByTranscript, setAiMessagesByTranscript] = useState<{
    [key: string]: { role: string; text: string }[];
  }>({});
  const [activeTab, setActiveTab] = useState<'transcript' | 'ai'>('transcript');
  const [loading, setLoading] = useState(false);
  const [audioLoading, setAudioLoading] = useState(false);
  const [leftPanelTab, setLeftPanelTab] = useState<'stats' | 'feedback' | 'costs'>('stats');
  const [feedbackType, setFeedbackType] = useState<'good' | 'bad' | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState('');
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [userFeedback, setUserFeedback] = useState<ConversationFeedbackEntry | null>(null);
  const [localTranscript, setLocalTranscript] = useState<Transcript | null>(transcript);
  const [debugLogOpen, setDebugLogOpen] = useState(false);
  const [debugMessageId, setDebugMessageId] = useState<string | null>(null);
  const [showCosts, setShowCosts] = useState(false);
  const [costsByMessageId, setCostsByMessageId] = useState<Record<string, AgentResponseLogSummary>>({});
  const [totalCost, setTotalCost] = useState<Record<string, number>>({
    total: 0,
    input_tokens: 0,
    output_tokens: 0,
  });
  const [costIncomplete, setCostIncomplete] = useState(false);

  useEffect(() => {
    setLocalTranscript(transcript);
  }, [transcript]);

  const chatContainerRef = useRef<HTMLDivElement>(null);
  const isCall = isCallTranscript(localTranscript);
  const { toast } = useToast();
  const [linkCopied, setLinkCopied] = useState(false);
  const { agentNameMap } = useAgentsList();
  const showAskGenAI = useFeatureFlagVisible(FeatureFlags.CONVERSATIONS.SHOW_ASK_GENAI);
  // Without the flag the assistant is gone, so the transcript is the only pane left
  const rightPanelTab = showAskGenAI ? activeTab : 'transcript';

  const headerAgentName = useMemo(() => {
    if (!localTranscript) return undefined;
    const fromApi = localTranscript.agent_name?.trim();
    if (fromApi) return fromApi;
    const fromProp = agentNameProp?.trim();
    if (fromProp) return fromProp;
    const fromAgentId =
      localTranscript.agent_id && agentNameMap[localTranscript.agent_id]
        ? agentNameMap[localTranscript.agent_id]
        : undefined;
    if (fromAgentId) return fromAgentId;
    return resolveAgentNameFromTranscript(localTranscript, agentNameMap);
  }, [localTranscript, agentNameProp, agentNameMap]);

  const supervisorId = useMemo(() => {
    if (!localTranscript) return undefined;
    return resolveSupervisorId(localTranscript);
  }, [localTranscript]);

  const supervisorDisplayName = useMemo(() => {
    if (!localTranscript) return undefined;
    const fromApi = localTranscript.supervisor_username?.trim();
    if (fromApi) return fromApi;
    return resolveSupervisorUsernameFromAttrs(localTranscript);
  }, [localTranscript]);

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
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
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
    setFeedbackMessage('');
  }, [localTranscript]);

  // keep persisted feedback
  useEffect(() => {
    if (!isOpen) {
      setIsEditing(false);
      setFeedbackType(null);
      setFeedbackMessage('');
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

  // Fetch agent response logs (token/cost) when dialog opens
  useEffect(() => {
    if (!isOpen || !localTranscript?.id) return;

    const totalCost: Record<string, number> = {
      total: 0,
      input_tokens: 0,
      output_tokens: 0,
    };

    // Fetch agent response logs
    fetchAgentResponseLogsByConversation(localTranscript.id).then((logs) => {
      const map: Record<string, AgentResponseLogSummary> = {};
      logs.forEach((log) => {
        map[log.transcript_message_id] = log;

        // Add cost to total cost
        totalCost.total += log.cost_usd ?? 0;
        totalCost.input_tokens += log.input_tokens ?? 0;
        totalCost.output_tokens += log.output_tokens ?? 0;
      });

      setCostsByMessageId(map);
      setTotalCost(totalCost);
      setCostIncomplete(logs.some((log) => log.cost_usd == null));
    });
  }, [isOpen, localTranscript?.id]);

  const handleSendMessage = async () => {
    if (!showAskGenAI || chatInput.trim() === '' || !localTranscript) return;

    const userMessage = { role: 'Me', text: chatInput };

    setAiMessagesByTranscript((prev) => ({
      ...prev,
      [localTranscript.id]: [...(prev[localTranscript.id] || []), userMessage],
    }));

    setChatInput('');
    setActiveTab('ai');
    setLoading(true);

    try {
      const response = await askAIQuestion(localTranscript.id, chatInput);
      const aiResponse = { role: 'GenAssist AI', text: response.answer };

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
            role: 'GenAssist AI',
            text: "Sorry, I couldn't process your request at the moment.",
          },
        ],
      }));
    } finally {
      setLoading(false);
    }
  };

  const handleFeedbackSubmit = async () => {
    if (!localTranscript || !feedbackType) {
      toast({
        title: 'Error',
        description: 'Please select a rating.',
        variant: 'destructive',
      });
      return;
    }

    setFeedbackSubmitting(true);

    try {
      const success = await submitConversationFeedback(localTranscript.id, feedbackType, feedbackMessage.trim());

      if (success) {
        const newFeedback = {
          feedback: feedbackType,
          feedback_message: feedbackMessage.trim(),
          feedback_timestamp: new Date().toISOString(),
          feedback_user_id: '', // set by the service
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
        setFeedbackMessage('');

        toast({
          title: 'Success',
          description: 'Feedback submitted successfully!',
        });
      } else {
        toast({
          title: 'Error',
          description: 'Failed to submit feedback. Please try again.',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to submit feedback. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setFeedbackSubmitting(false);
    }
  };

  const handleEditFeedback = () => {
    if (userFeedback) {
      setFeedbackType(userFeedback.feedback || null);
      setFeedbackMessage(userFeedback.feedback_message);
      setIsEditing(true);
    }
  };

  const handleMessageFeedback = async (messageId: string, feedback: 'good' | 'bad') => {
    if (!localTranscript?.id) return;
    // Rating only — don't pass a comment so an existing comment is preserved.
    const success = await submitMessageFeedback(messageId, feedback);
    if (success) {
      setLocalTranscript((currentTranscript) => {
        if (!currentTranscript) return null;
        const base = currentTranscript.messages || [];
        const newTranscriptEntries = base.map((entry) => {
          if (entry.message_id !== messageId) return entry;
          const arr = Array.isArray(entry.feedback) ? [...entry.feedback] : [];
          if (arr.length > 0) {
            // Set the rating on the latest entry, keeping its comment.
            const idx = arr.length - 1;
            arr[idx] = { ...arr[idx], feedback };
          } else {
            arr.push({
              feedback,
              feedback_message: '',
              feedback_timestamp: new Date().toISOString(),
              feedback_user_id: '',
            });
          }
          return { ...entry, feedback: arr };
        });
        return { ...currentTranscript, messages: newTranscriptEntries, transcript: newTranscriptEntries };
      });
    }
  };

  if (!localTranscript) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl 2xl:max-w-[1120px] min-[1920px]:max-w-[1340px]">
        <DialogHeader>
          <DialogTitle className="flex flex-col gap-1.5 items-start">
            <span className="flex items-center gap-2">
              {isCall ? <PlayCircle className="w-5 h-5 shrink-0" /> : <MessageSquare className="w-5 h-5 shrink-0" />}
              <span>
                {isCall ? 'Call' : 'Chat'} #{(localTranscript?.metadata?.title ?? '----').slice(-4)}
              </span>
              {supervisorId && (
                <div className="ml-1 inline-flex items-center gap-1.5 rounded-full bg-blue-100 dark:bg-blue-500/20 px-3 py-1.5 text-xs font-medium text-blue-800 dark:text-blue-400">
                  <span className="flex items-center gap-1.5 leading-none">
                    <span>Supervisor:</span>
                    <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-blue-200 text-[10px] font-semibold uppercase text-blue-800">
                      {(supervisorDisplayName?.charAt(0) || supervisorId.charAt(0) || 'S').toUpperCase()}
                    </span>
                    <span>{supervisorDisplayName || supervisorId}</span>
                  </span>
                </div>
              )}
              <Button
                variant="ghost"
                size="sm"
                className={`ml-auto h-7 w-7 p-0 transition-colors ${linkCopied ? 'text-green-600 dark:text-green-400' : ''}`}
                title="Copy share link"
                disabled={linkCopied}
                onClick={async () => {
                  const url = `${window.location.origin}/transcripts?conversation=${localTranscript?.id}`;
                  await navigator.clipboard.writeText(url);
                  setLinkCopied(true);
                  toast({ title: 'Link copied to clipboard', description: 'Anyone with this link can open the conversation.' });
                  setTimeout(() => setLinkCopied(false), 2000);
                }}
              >
                {linkCopied ? <Check className="h-4 w-4" /> : <Share2 className="h-4 w-4" />}
              </Button>
            </span>
            {headerAgentName ? (
              <span className="flex items-center gap-1.5 text-sm font-normal text-muted-foreground pr-10">
                {headerAgentName}
              </span>
            ) : null}
          </DialogTitle>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-[350px_1fr] gap-6 items-start">
          <div className="space-y-4 flex flex-col">
            {/* Left Panel Toggle */}
            <Tabs
              value={leftPanelTab}
              onValueChange={(value) => setLeftPanelTab(value as 'stats' | 'feedback' | 'costs')}
              className="w-full"
            >
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="stats">Stats</TabsTrigger>
                <TabsTrigger value="feedback">Feedback</TabsTrigger>
                <TabsTrigger value="costs">Costs</TabsTrigger>
              </TabsList>
            </Tabs>

            <MetricCards
              duration={Number(localTranscript.duration)}
              wordCount={localTranscript.metrics.wordCount}
              sentiment={getEffectiveSentiment(localTranscript)}
              speakingRatio={localTranscript.metrics.speakingRatio}
            />

            {leftPanelTab === 'stats' && (
              <>
                <div className="flex items-center gap-2 px-2 justify-between">
                  <div className="flex flex-row items-center gap-2">
                    <Megaphone className="w-4 h-4 text-yellow-500" />
                    <span className="text-sm font-medium"> Conversation Tone</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {localTranscript.metrics.tone.map((tone, index) => (
                      <span key={index} className="px-2 py-1 bg-muted text-foreground rounded-full text-xs font-bold">
                        {tone.toLowerCase()}
                      </span>
                    ))}
                  </div>
                </div>

                {isCall && <TranscriptAudioPlayer isLoading={audioLoading} audioSrc={audioSrc} />}

                <ScoreCards metrics={localTranscript.metrics} />
              </>
            )}

            {leftPanelTab === 'feedback' && (
              <div className="space-y-4">
                {userFeedback && !isEditing ? (
                  // Display saved feedback
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-sm font-medium mb-3">Rate</h4>
                      <div className="flex items-center gap-2">
                        {userFeedback.feedback === 'good' ? (
                          <>
                            <ThumbsUp className="w-5 h-5 text-green-600 dark:text-green-400" />
                            <span className="text-sm font-medium text-green-600 dark:text-green-400">Good</span>
                          </>
                        ) : (
                          <>
                            <ThumbsDown className="w-5 h-5 text-red-600 dark:text-red-400" />
                            <span className="text-sm font-medium text-red-600 dark:text-red-400">Bad</span>
                          </>
                        )}
                      </div>
                    </div>

                    <div>
                      <h4 className="text-sm font-medium mb-2">Feedback for this message</h4>
                      <p className="text-xs text-muted-foreground mb-2">
                        {formatFeedbackDate(userFeedback.feedback_timestamp)}
                      </p>
                      <p className="text-sm text-muted-foreground leading-relaxed">{userFeedback.feedback_message}</p>
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
                          type="button"
                          onClick={() => setFeedbackType('good')}
                          className={`p-2 rounded transition-all ${
                            feedbackType === 'good'
                              ? 'bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400'
                              : 'bg-muted text-muted-foreground hover:text-muted-foreground'
                          }`}
                        >
                          <ThumbsUp className="w-4 h-4" />
                        </button>

                        <button
                          type="button"
                          onClick={() => setFeedbackType('bad')}
                          className={`p-2 rounded transition-all ${
                            feedbackType === 'bad'
                              ? 'bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400'
                              : 'bg-muted text-muted-foreground hover:text-muted-foreground'
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
                        disabled={!feedbackType || feedbackSubmitting}
                        className="flex-1 bg-blue-600 text-white hover:bg-blue-700"
                      >
                        {feedbackSubmitting ? 'Submitting...' : 'Save'}
                      </Button>

                      {isEditing && (
                        <Button
                          onClick={() => {
                            setIsEditing(false);
                            setFeedbackType(null);
                            setFeedbackMessage('');
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

            {leftPanelTab === 'costs' && (
              <>
              <div className="flex items-center gap-2 px-2 justify-between">
                  <div className="flex flex-row items-center gap-2">
                    <Coins className="w-4 h-4 text-yellow-500" />
                    <span className="text-sm font-medium">Show costs per message</span>
                  </div>
                  <Switch checked={showCosts} onCheckedChange={setShowCosts} />
                </div>
              <div className="p-3 rounded-lg">
                <h4 className="text-sm font-medium mb-2">Conversation Costs</h4>
                <p className="text-sm text-muted-foreground flex justify-between"><span>Input Tokens:</span> <b>{totalCost.input_tokens}</b></p>
                <p className="text-sm text-muted-foreground flex justify-between"><span>Output Tokens:</span> <b>{totalCost.output_tokens}</b></p>
                <p
                  className="text-sm text-muted-foreground flex justify-between"
                  title={
                    costIncomplete
                      ? 'Some messages have no cost recorded. The real total is higher than this.'
                      : undefined
                  }
                >
                  <span>Total Cost:</span>{' '}
                  <b>
                    {costIncomplete ? '≥ ' : ''}${totalCost.total.toFixed(6)}
                  </b>
                </p>
              </div>
              </>
            )}
          </div>

          <div className="flex flex-col">
            <Tabs
              value={rightPanelTab}
              onValueChange={(value) => setActiveTab(value as 'transcript' | 'ai')}
              className="pb-1"
            >
              <TabsList className={`grid w-full ${showAskGenAI ? 'grid-cols-2' : 'grid-cols-1'}`}>
                <TabsTrigger value="transcript">Transcript</TabsTrigger>
                {showAskGenAI && <TabsTrigger value="ai">Ask GenAI</TabsTrigger>}
              </TabsList>
            </Tabs>
            <div className="flex-1 flex flex-col bg-secondary/30 rounded-lg overflow-hidden">
              {rightPanelTab === 'transcript' ? (
                <TranscriptThread
                  transcript={localTranscript}
                  isCall={isCall}
                  showCosts={showCosts}
                  costsByMessageId={costsByMessageId}
                  onMessageFeedback={handleMessageFeedback}
                  onTranscriptChange={setLocalTranscript}
                  onDebugMessage={(messageId) => {
                    setDebugMessageId(messageId);
                    setDebugLogOpen(true);
                  }}
                  className={
                    isCall
                      ? 'h-[550px] 2xl:h-[min(70vh,660px)] min-[1920px]:h-[min(72vh,780px)]'
                      : 'h-[460px] 2xl:h-[min(64vh,560px)] min-[1920px]:h-[min(68vh,680px)]'
                  }
                />
              ) : (
                <div
                  ref={chatContainerRef}
                  className={`p-3 overflow-y-auto text-[13px] sm:text-[12px] ${
                    isCall
                      ? 'h-[500px] 2xl:h-[min(64vh,600px)] min-[1920px]:h-[min(66vh,720px)]'
                      : 'h-[400px] 2xl:h-[min(58vh,500px)] min-[1920px]:h-[min(62vh,620px)]'
                  }`}
                >
                  {aiMessagesByTranscript[localTranscript.id]?.length > 0 ? (
                    <div className="space-y-2">
                      {aiMessagesByTranscript[localTranscript.id]?.map((msg, index) => (
                        <div key={index} className={`flex ${msg.role === 'Me' ? 'justify-end' : 'justify-start'}`}>
                          <div
                            className={`p-2 rounded-lg max-w-[75%] sm:max-w-[90%] leading-tight break-words ${
                              msg.role === 'Me' ? 'bg-blue-100 text-blue-900' : 'bg-green-100 text-green-900'
                            }`}
                          >
                            <span className="block text-[11px] text-muted-foreground font-medium">{msg.role}</span>
                            {msg.text}
                          </div>
                        </div>
                      ))}
                      {loading && (
                        <div className="flex justify-start">
                          <div className="p-2 rounded-lg bg-muted text-foreground max-w-[75%]">
                            <span className="block text-[11px] text-muted-foreground font-medium">Gen AI</span>
                            Thinking...
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="flex flex-1 flex-col justify-center items-center text-muted-foreground">
                      <BotMessageSquare className="w-12 h-12 text-muted-foreground" />
                      <p className="text-sm mt-2">What can I help with?</p>
                    </div>
                  )}
                </div>
              )}
            </div>
            {rightPanelTab === 'ai' && (
              <div className="mt-2 flex items-center gap-2 bg-secondary/30 p-2 rounded-lg">
                <Input
                  className="flex-1"
                  type="text"
                  placeholder="Ask GenAI"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                />
                <Button onClick={handleSendMessage} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white">
                  Send
                </Button>
              </div>
            )}
          </div>
        </div>

        <AgentResponseLogDialog
          isOpen={debugLogOpen}
          onOpenChange={(open) => {
            setDebugLogOpen(open);
            if (!open) {
              setDebugMessageId(null);
            }
          }}
          messageId={debugMessageId}
        />
      </DialogContent>
    </Dialog>
  );
}
