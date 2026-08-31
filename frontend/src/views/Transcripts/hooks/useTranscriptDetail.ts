import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  getAudioUrl,
  submitConversationFeedback,
  submitMessageFeedback,
  fetchAgentResponseLogsByConversation,
  type AgentResponseLogSummary,
} from '@/services/transcripts';
import { Transcript, ConversationFeedbackEntry } from '@/interfaces/transcript.interface';
import { askAIQuestion } from '@/services/aiChat';
import { useToast } from '@/hooks/useToast';
import { useAgentsList } from '@/views/Analytics/hooks/useAgentsList';
import { useFeatureFlagVisible } from '@/components/featureFlag';
import { FeatureFlags } from '@/config/featureFlags';

export type TranscriptLeftPanelTab = 'stats' | 'feedback' | 'costs';
export type TranscriptRightPanelTab = 'transcript' | 'ai';

function valueForKey(
  attrs: Record<string, unknown> | undefined,
  ...candidates: string[]
): string | undefined {
  if (!attrs) return undefined;
  const entries = Object.entries(attrs);
  for (const c of candidates) {
    const cl = c.toLowerCase();
    const hit = entries.find(([k]) => k.toLowerCase() === cl);
    const v = hit?.[1];
    if (typeof v === 'string' && v.trim()) return v.trim();
  }
  return undefined;
}

function resolveAgentNameFromTranscript(
  transcript: Transcript,
  agentNameMap: Record<string, string>
): string | undefined {
  const attrs = transcript.custom_attributes;
  if (!attrs) return undefined;

  const fromNameKeys = valueForKey(attrs, 'agent_name', 'agentName', 'Agent Name', 'genassist_agent_name');
  if (fromNameKeys) return fromNameKeys;

  const idVal = valueForKey(attrs, 'agent_id', 'agentId', 'Agent ID', 'genassist_agent_id');
  if (idVal && agentNameMap[idVal]) return agentNameMap[idVal];

  return undefined;
}

function resolveSupervisorId(transcript: Transcript): string | undefined {
  const directSupervisorId = transcript.supervisor_id?.trim();
  if (directSupervisorId) return directSupervisorId;

  return valueForKey(
    transcript.custom_attributes,
    'supervisor_id',
    'supervisorId',
    'operator_id',
    'operatorId'
  );
}

function resolveSupervisorUsernameFromAttrs(transcript: Transcript): string | undefined {
  return valueForKey(
    transcript.custom_attributes,
    'supervisor_username',
    'supervisor_user_name',
    'operator_username',
    'operator_user_name'
  );
}

export const isCallTranscript = (transcript: Transcript | null) => {
  if (!transcript) return false;
  return Boolean(transcript.recording_id) || Boolean(transcript.metadata?.isCall);
};

type UseTranscriptDetailOptions = {
  transcript: Transcript | null;
  /**
   * The detail surface is visible — a dialog that is open, or a pane that is mounted.
   * Gates the fetches (audio logs, costs) and the form resets that used to key off the
   * dialog's `isOpen`.
   */
  isActive: boolean;
  /** When the list is filtered to one agent, its name is used as a header fallback. */
  agentName?: string;
};

/**
 * Everything `TranscriptDialog` used to own: the local copy of the transcript, the
 * stats/feedback/costs panel state, the Ask GenAI thread and the feedback handlers.
 *
 * Extracted so the same conversation detail can render either as a dialog or as the
 * detail columns of the Conversations workspace.
 */
export function useTranscriptDetail({ transcript, isActive, agentName }: UseTranscriptDetailOptions) {
  const [audioSrc, setAudioSrc] = useState<string>('');
  const [chatInput, setChatInput] = useState<string>('');
  const [aiMessagesByTranscript, setAiMessagesByTranscript] = useState<{
    [key: string]: { role: string; text: string }[];
  }>({});
  const [activeTab, setActiveTab] = useState<TranscriptRightPanelTab>('transcript');
  const [loading, setLoading] = useState(false);
  const [audioLoading, setAudioLoading] = useState(false);
  const [leftPanelTab, setLeftPanelTab] = useState<TranscriptLeftPanelTab>('stats');
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
  const [linkCopied, setLinkCopied] = useState(false);

  useEffect(() => {
    setLocalTranscript(transcript);
  }, [transcript]);

  const chatContainerRef = useRef<HTMLDivElement>(null);
  const isCall = isCallTranscript(localTranscript);
  const { toast } = useToast();
  const { agentNameMap } = useAgentsList();
  const showAskGenAI = useFeatureFlagVisible(FeatureFlags.CONVERSATIONS.SHOW_ASK_GENAI);
  // Without the flag the assistant is gone, so the transcript is the only pane left
  const rightPanelTab: TranscriptRightPanelTab = showAskGenAI ? activeTab : 'transcript';

  const headerAgentName = useMemo(() => {
    if (!localTranscript) return undefined;
    const fromApi = localTranscript.agent_name?.trim();
    if (fromApi) return fromApi;
    const fromProp = agentName?.trim();
    if (fromProp) return fromProp;
    const fromAgentId =
      localTranscript.agent_id && agentNameMap[localTranscript.agent_id]
        ? agentNameMap[localTranscript.agent_id]
        : undefined;
    if (fromAgentId) return fromAgentId;
    return resolveAgentNameFromTranscript(localTranscript, agentNameMap);
  }, [localTranscript, agentName, agentNameMap]);

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
      .catch(() => {
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

  // Check for existing user feedback when the transcript loads
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
    if (!isActive) {
      setIsEditing(false);
      setFeedbackType(null);
      setFeedbackMessage('');
    }
  }, [isActive]);

  // When the detail becomes visible, hydrate from transcript if available
  const feedbackCount = Array.isArray(localTranscript?.feedback) ? localTranscript.feedback.length : 0;
  useEffect(() => {
    if (!isActive) return;
    if (Array.isArray(localTranscript?.feedback) && localTranscript.feedback.length > 0) {
      setUserFeedback(localTranscript.feedback[localTranscript.feedback.length - 1]);
    }
  }, [isActive, feedbackCount, localTranscript?.feedback]);

  // Fetch agent response logs (token/cost) for the visible conversation
  useEffect(() => {
    if (!isActive || !localTranscript?.id) return;

    const totals: Record<string, number> = {
      total: 0,
      input_tokens: 0,
      output_tokens: 0,
    };

    fetchAgentResponseLogsByConversation(localTranscript.id).then((logs) => {
      const map: Record<string, AgentResponseLogSummary> = {};
      logs.forEach((log) => {
        map[log.transcript_message_id] = log;

        // Add cost to total cost
        totals.total += log.cost_usd ?? 0;
        totals.input_tokens += log.input_tokens ?? 0;
        totals.output_tokens += log.output_tokens ?? 0;
      });

      setCostsByMessageId(map);
      setTotalCost(totals);
    });
  }, [isActive, localTranscript?.id]);

  const sendAiMessage = useCallback(async () => {
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
    } catch {
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
  }, [showAskGenAI, chatInput, localTranscript]);

  const submitFeedback = useCallback(async () => {
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

        // update local state so the panel reflects feedback immediately
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
    } catch {
      toast({
        title: 'Error',
        description: 'Failed to submit feedback. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setFeedbackSubmitting(false);
    }
  }, [localTranscript, feedbackType, feedbackMessage, toast]);

  const startEditFeedback = useCallback(() => {
    if (userFeedback) {
      setFeedbackType(userFeedback.feedback || null);
      setFeedbackMessage(userFeedback.feedback_message);
      setIsEditing(true);
    }
  }, [userFeedback]);

  const cancelEditFeedback = useCallback(() => {
    setIsEditing(false);
    setFeedbackType(null);
    setFeedbackMessage('');
  }, []);

  const handleMessageFeedback = useCallback(
    async (messageId: string, feedback: 'good' | 'bad') => {
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
    },
    [localTranscript?.id]
  );

  const openDebugMessage = useCallback((messageId: string) => {
    setDebugMessageId(messageId);
    setDebugLogOpen(true);
  }, []);

  const closeDebugLog = useCallback((open: boolean) => {
    setDebugLogOpen(open);
    if (!open) setDebugMessageId(null);
  }, []);

  const copyShareLink = useCallback(async () => {
    if (!localTranscript?.id) return;
    const url = `${window.location.origin}/transcripts?conversation=${localTranscript.id}`;
    await navigator.clipboard.writeText(url);
    setLinkCopied(true);
    toast({
      title: 'Link copied to clipboard',
      description: 'Anyone with this link can open the conversation.',
    });
    setTimeout(() => setLinkCopied(false), 2000);
  }, [localTranscript?.id, toast]);

  return {
    transcript: localTranscript,
    setTranscript: setLocalTranscript,
    isCall,
    headerAgentName,
    supervisorId,
    supervisorDisplayName,
    linkCopied,
    copyShareLink,
    audioSrc,
    audioLoading,
    leftPanelTab,
    setLeftPanelTab,
    activeTab,
    setActiveTab,
    rightPanelTab,
    showAskGenAI,
    chatInput,
    setChatInput,
    aiMessages: localTranscript ? aiMessagesByTranscript[localTranscript.id] ?? [] : [],
    aiLoading: loading,
    sendAiMessage,
    chatContainerRef,
    showCosts,
    setShowCosts,
    costsByMessageId,
    totalCost,
    userFeedback,
    isEditing,
    feedbackType,
    setFeedbackType,
    feedbackMessage,
    setFeedbackMessage,
    feedbackSubmitting,
    submitFeedback,
    startEditFeedback,
    cancelEditFeedback,
    handleMessageFeedback,
    debugLogOpen,
    debugMessageId,
    openDebugMessage,
    closeDebugLog,
  };
}

export type TranscriptDetailController = ReturnType<typeof useTranscriptDetail>;
