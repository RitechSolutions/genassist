import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type Dispatch,
  type SetStateAction,
} from 'react';
import { ThumbsUp, ThumbsDown, User, Coins, Flag } from 'lucide-react';

import { Transcript, ConversationFeedbackEntry } from '@/interfaces/transcript.interface';
import { submitMessageFeedback, type AgentResponseLogSummary } from '@/services/transcripts';
import { useToast } from '@/hooks/useToast';
import { cn } from '@/helpers/utils';
import { ConversationEntryWrapper } from '@/views/ActiveConversations/common/ConversationEntryWrapper';
import { MessageFeedbackPopover } from './MessageFeedbackPopover';
import { formatMessageTime, formatCallTimestamp, formatDateTime } from '../helpers/formatting';

function MessageFeedbackButton({
  messageId,
  localTranscript,
  setLocalTranscript,
  collisionBoundary,
  onOpenChange,
}: {
  messageId: string;
  localTranscript: Transcript | null;
  setLocalTranscript: Dispatch<SetStateAction<Transcript | null>>;
  collisionBoundary: Element | null;
  onOpenChange?: (open: boolean) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [text, setText] = useState('');
  const { toast } = useToast();

  const handleOpenChange = (open: boolean) => {
    setIsOpen(open);
    onOpenChange?.(open);

    if (open) {
      const collection = localTranscript?.messages || [];
      const message = collection.find((entry) => entry.message_id === messageId);
      const feedbackArr = Array.isArray(message?.feedback) ? (message?.feedback as ConversationFeedbackEntry[]) : [];
      const lastFeedback = feedbackArr.length > 0 ? feedbackArr[feedbackArr.length - 1] : null;
      setText(lastFeedback?.feedback_message || '');
    }
  };

  const message = localTranscript?.messages?.find((entry) => entry.message_id === messageId);
  const feedbackArr = Array.isArray(message?.feedback) ? (message?.feedback as ConversationFeedbackEntry[]) : [];
  const lastFeedback = feedbackArr.length > 0 ? feedbackArr[feedbackArr.length - 1] : null;
  const hasFeedbackMessage = Boolean(lastFeedback?.feedback_message?.trim());

  const handleClose = () => {
    handleOpenChange(false);
    setText('');
  };

  const handleSave = async () => {
    if (!messageId || !localTranscript) return;

    // A comment must never create or change a thumbs rating, so don't send one.
    const success = await submitMessageFeedback(messageId, undefined, text);

    if (success) {
      setLocalTranscript((currentTranscript) => {
        if (!currentTranscript) return null;
        const b = currentTranscript.messages || [];
        const newTranscriptEntries = b.map((entry) => {
          if (entry.message_id !== messageId) return entry;
          const arr = Array.isArray(entry.feedback) ? [...entry.feedback] : [];
          if (arr.length > 0) {
            // Attach the comment to the latest feedback entry, keeping its rating.
            const idx = arr.length - 1;
            arr[idx] = { ...arr[idx], feedback_message: text };
          } else {
            // Comment with no rating yet (feedback "" => no thumbs).
            arr.push({
              feedback: '',
              feedback_message: text,
              feedback_timestamp: new Date().toISOString(),
              feedback_user_id: '',
            });
          }
          return { ...entry, feedback: arr };
        });
        return { ...currentTranscript, messages: newTranscriptEntries, transcript: newTranscriptEntries };
      });

      toast({ title: 'Success', description: 'Feedback message saved.' });
      handleClose();
    } else {
      toast({ title: 'Error', description: 'Failed to save feedback.', variant: 'destructive' });
    }
  };

  return (
    <MessageFeedbackPopover
      isOpen={isOpen}
      hasFeedbackMessage={hasFeedbackMessage}
      text={text}
      collisionBoundary={collisionBoundary}
      onOpenChange={handleOpenChange}
      onTextChange={setText}
      onSave={handleSave}
      onCancel={handleClose}
    />
  );
}

export type TranscriptThreadVariant = 'full' | 'compact';

type TranscriptThreadProps = {
  transcript: Transcript;
  /** Call transcripts stamp each message with a call offset instead of a wall-clock time. */
  isCall?: boolean;
  /**
   * 'compact' renders the thread read-only — no rating controls, no comment popover and no
   * debug/cost row — for embedding inside a dialog that owns those actions itself.
   */
  variant?: TranscriptThreadVariant;
  /** Ringed, labelled "Reported" and scrolled to the middle of the pane on mount. */
  highlightMessageId?: string | null;
  showCosts?: boolean;
  costsByMessageId?: Record<string, AgentResponseLogSummary>;
  onMessageFeedback?: (messageId: string, feedback: 'good' | 'bad') => void;
  /** Lets the comment popover write its result back into the owner's transcript state. */
  onTranscriptChange?: Dispatch<SetStateAction<Transcript | null>>;
  onDebugMessage?: (messageId: string) => void;
  /** Applied to the scroll container, so the caller decides how tall the thread is. */
  className?: string;
  style?: CSSProperties;
};

/**
 * The conversation thread on its own — message bubbles, per-message feedback controls and the
 * takeover/finalized markers. Extracted from `TranscriptDialog` so other surfaces (e.g. the
 * Reported Feedback dialog) can embed the same thread instead of navigating to Transcripts.
 */
export function TranscriptThread({
  transcript,
  isCall = false,
  variant = 'full',
  highlightMessageId = null,
  showCosts = false,
  costsByMessageId,
  onMessageFeedback,
  onTranscriptChange,
  onDebugMessage,
  className,
  style,
}: TranscriptThreadProps) {
  const [openPopoverMessageId, setOpenPopoverMessageId] = useState<string | null>(null);
  const [scrollEl, setScrollEl] = useState<HTMLDivElement | null>(null);
  const messageRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const isInteractive = variant === 'full';
  const messages = useMemo(() => transcript.messages ?? [], [transcript.messages]);
  const costs = costsByMessageId ?? {};

  // Centre the flagged message inside this pane only — scrollIntoView() would walk up the
  // ancestor chain and drag the surrounding dialog along with it.
  useEffect(() => {
    if (!highlightMessageId || !scrollEl) return;

    const raf = requestAnimationFrame(() => {
      const node = messageRefs.current.get(highlightMessageId);
      if (!node) return;

      const top = node.offsetTop - scrollEl.clientHeight / 2 + node.offsetHeight / 2;
      scrollEl.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
    });

    return () => cancelAnimationFrame(raf);
  }, [highlightMessageId, transcript.id, messages.length, scrollEl]);

  return (
    <div
      ref={setScrollEl}
      className={cn('relative overflow-y-auto p-3 text-[13px] sm:text-[12px]', className)}
      style={style}
    >
      <div className="space-y-2">
        {transcript.timestamp && (
          <div className="flex justify-center mb-3">
            <div className="px-3 py-1 rounded-full bg-muted text-muted-foreground text-xs">
              {formatDateTime(transcript.timestamp)}
            </div>
          </div>
        )}
        {messages.map((entry, index) => {
          const entryObj = typeof entry === 'string' ? JSON.parse(entry) : entry;
          const entryType = entryObj.type || '';

          if (
            entryType === 'takeover' ||
            (entryObj.speaker === 'Unknown' && entryObj.text === '' && entryObj.start_time === 0)
          ) {
            return (
              <div className="flex justify-center my-3" key={`takeover-${index}-${entryObj.create_time || index}`}>
                <div className="px-3 py-1.5 rounded-full bg-blue-100 dark:bg-blue-500/20 text-blue-800 dark:text-blue-400 text-xs font-medium flex items-center">
                  <User className="w-3 h-3 mr-1" />
                  Supervisor took over
                </div>
              </div>
            );
          }

          // Skip empty messages
          if ((entryObj.text === '' || !entryObj.text) && (entryObj.speaker === '' || !entryObj.speaker)) {
            return null;
          }

          const isAgent = ['Agent', 'agent'].includes(entryObj.speaker);
          const messageId = entryObj.message_id as string | undefined;
          const messageFeedbackArr = Array.isArray(entryObj.feedback)
            ? (entryObj.feedback as ConversationFeedbackEntry[])
            : [];
          const hasGood = messageFeedbackArr.some((f) => f.feedback === 'good');
          const hasBad = messageFeedbackArr.some((f) => f.feedback === 'bad');
          const hasComment = messageFeedbackArr.some((f) => Boolean(f.feedback_message && f.feedback_message.trim()));
          // Keep the controls pinned once there's any feedback (rating or comment),
          // so the comment indicator doesn't vanish when the hover ends.
          const hasFeedback = hasGood || hasBad || hasComment;
          const speakerName = isAgent ? 'Operator' : 'Customer';
          const isHighlighted = Boolean(messageId && messageId === highlightMessageId);

          return (
            <div
              key={index}
              ref={(node) => {
                if (!messageId) return;
                if (node) messageRefs.current.set(messageId, node);
                else messageRefs.current.delete(messageId);
              }}
              className={`flex flex-col ${isAgent ? 'items-end' : 'items-start'} group relative`}
            >
              <span className="flex items-center gap-1.5 text-[11px] text-foreground font-medium mb-1">
                {speakerName}
                {isHighlighted && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:bg-amber-500/20 dark:text-amber-400">
                    <Flag className="h-2.5 w-2.5" />
                    Reported
                  </span>
                )}
              </span>
              <div className="relative">
                {isInteractive && isAgent && messageId && (
                  <div
                    className={`absolute right-full mr-2 top-1/2 -translate-y-1/2 ${
                      hasFeedback || openPopoverMessageId === messageId ? 'flex' : 'hidden group-hover:flex'
                    } items-center gap-2 z-10`}
                  >
                    {hasGood ? (
                      <div className="flex items-center bg-card rounded-lg shadow-sm border border-green-200 dark:border-green-500/30 p-2">
                        <ThumbsUp className="w-4 h-4 text-green-600 dark:text-green-400" />
                      </div>
                    ) : hasBad ? (
                      <div className="flex items-center bg-card rounded-lg shadow-sm border border-red-200 dark:border-red-500/30 p-2">
                        <ThumbsDown className="w-4 h-4 text-red-600 dark:text-red-400" />
                      </div>
                    ) : (
                      <div className="flex items-center bg-card rounded-lg shadow-sm border border-border">
                        <button
                          className="p-2 hover:bg-muted rounded-l-lg"
                          title="Good response"
                          onClick={() => onMessageFeedback?.(messageId, 'good')}
                        >
                          <ThumbsUp className="w-4 h-4 text-yellow-500" />
                        </button>
                        <div className="h-4 w-px bg-muted" />
                        <button
                          className="p-2 hover:bg-muted rounded-r-lg"
                          title="Bad response"
                          onClick={() => onMessageFeedback?.(messageId, 'bad')}
                        >
                          <ThumbsDown className="w-4 h-4 text-yellow-500" />
                        </button>
                      </div>
                    )}
                    {onTranscriptChange && (
                      <MessageFeedbackButton
                        messageId={messageId}
                        localTranscript={transcript}
                        setLocalTranscript={onTranscriptChange}
                        collisionBoundary={scrollEl}
                        onOpenChange={(open) => setOpenPopoverMessageId(open ? messageId : null)}
                      />
                    )}
                  </div>
                )}
                <div className="p-2 flex flex-col gap-1 max-w-[400px] 2xl:max-w-[500px] min-[1920px]:max-w-[600px]">
                  <div
                    className={cn(
                      'p-2 rounded-lg leading-tight break-words inline-block z-10',
                      isAgent
                        ? 'bg-blue-600 text-white rounded-tl-lg rounded-tr-none'
                        : 'bg-muted text-foreground rounded-tr-lg rounded-tl-none',
                      isHighlighted &&
                        'ring-2 ring-amber-400 ring-offset-2 ring-offset-background dark:ring-amber-500'
                    )}
                  >
                    <ConversationEntryWrapper entry={entryObj} conversationId={transcript.id} />

                    <div className="flex items-center justify-end">
                      <span
                        className={`block text-[10px] text-right mt-1 ${
                          isAgent ? 'text-white/80' : 'text-muted-foreground'
                        }`}
                      >
                        {isCall ? formatCallTimestamp(entryObj.start_time) : formatMessageTime(entryObj.create_time)}
                      </span>
                    </div>
                  </div>

                  {isInteractive && isAgent && messageId && (
                    <div className="flex flex-row gap-1 px-3 py-2 pt-3 rounded-b-lg justify-between w-full bg-gray-300/50 text-black/80 -mt-3 z-9">
                      <button
                        type="button"
                        className="text-[10px] underline self-end"
                        onClick={() => onDebugMessage?.(messageId)}
                      >
                        Debug response
                      </button>
                      {showCosts && costs[messageId] && (
                        <div className={`mt-1 text-[10px] ${isAgent ? 'text-black/80' : 'text-gray-600'}`}>
                          Tokens Input/Output:
                          <span className="font-bold">{costs[messageId].input_tokens ?? '—'}</span>/
                          <span className="font-bold">{costs[messageId].output_tokens ?? '—'}</span>,
                          <Coins className="w-2 h-2 inline-block" /> Cost:{' '}
                          <span className="font-bold">
                            {costs[messageId].cost_usd == null ? '—' : `$${costs[messageId].cost_usd.toFixed(6)}`}
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
        {transcript.status === 'finalized' && (
          <div className="flex justify-center my-3">
            <div className="px-3 py-1.5 rounded-full bg-blue-100 dark:bg-blue-500/20 text-blue-800 dark:text-blue-400 text-xs font-medium flex items-center">
              Conversation Finalized
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
