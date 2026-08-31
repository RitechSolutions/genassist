import { AssistantComposer } from '@/components/AssistantComposer';
import { AssistantEmptyState, type AssistantSuggestion } from '@/components/AssistantEmptyState';
import { cn } from '@/helpers/utils';

import type { TranscriptDetailController } from '../../hooks/useTranscriptDetail';
import { TranscriptThread } from '../TranscriptThread';

const QUICK_QUESTIONS = ['Summarize this conversation', 'How did the agent perform?'];

type TranscriptConversationPanelProps = {
  controller: TranscriptDetailController;
  /**
   * `true` makes the thread grow to fill its parent (page layout); `false` keeps the
   * dialog's fixed viewport-relative heights.
   */
  fill?: boolean;
  className?: string;
};

/**
 * The transcript (or the assistant) for a finalized conversation. Which one is showing is driven
 * by the switch in `TranscriptDetailTitle`, so this panel is all conversation and no chrome.
 */
export function TranscriptConversationPanel({
  controller,
  fill = false,
  className,
}: TranscriptConversationPanelProps) {
  const {
    transcript,
    setTranscript,
    isCall,
    rightPanelTab,
    showAskGenAI,
    chatInput,
    setChatInput,
    aiMessages,
    aiLoading,
    sendAiMessage,
    chatContainerRef,
    showCosts,
    costsByMessageId,
    handleMessageFeedback,
    openDebugMessage,
  } = controller;

  if (!transcript) return null;

  // The dialog sizes the thread explicitly; the +44px over the previous values is the tab row
  // that now lives in the header, so the dialog keeps its overall height.
  const threadHeight = fill
    ? 'flex-1 min-h-0'
    : isCall
      ? 'h-[594px] 2xl:h-[min(70vh,704px)] min-[1920px]:h-[min(72vh,824px)]'
      : 'h-[504px] 2xl:h-[min(64vh,604px)] min-[1920px]:h-[min(68vh,724px)]';

  const quickQuestions: AssistantSuggestion[] = QUICK_QUESTIONS.map((label) => ({
    label,
    onSelect: () => sendAiMessage(label),
  }));

  const aiHeight = fill
    ? 'flex-1 min-h-0'
    : isCall
      ? 'h-[544px] 2xl:h-[min(64vh,644px)] min-[1920px]:h-[min(66vh,764px)]'
      : 'h-[444px] 2xl:h-[min(58vh,544px)] min-[1920px]:h-[min(62vh,664px)]';

  return (
    <div className={cn('flex flex-col', fill && 'h-full min-h-0', className)}>
      <div className={cn('flex-1 flex flex-col bg-secondary/30 rounded-lg overflow-hidden', fill && 'min-h-0')}>
        {rightPanelTab === 'transcript' ? (
          <TranscriptThread
            transcript={transcript}
            isCall={isCall}
            showCosts={showCosts}
            costsByMessageId={costsByMessageId}
            onMessageFeedback={handleMessageFeedback}
            onTranscriptChange={setTranscript}
            onDebugMessage={openDebugMessage}
            className={threadHeight}
          />
        ) : (
          <div
            ref={chatContainerRef}
            className={cn('p-3 overflow-y-auto text-[13px] sm:text-[12px]', aiHeight)}
          >
            {aiMessages.length > 0 ? (
              <div className="space-y-2">
                {aiMessages.map((msg, index) => (
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
                {aiLoading && (
                  <div className="flex justify-start">
                    <div className="p-2 rounded-lg bg-muted text-foreground max-w-[75%]">
                      <span className="block text-[11px] text-muted-foreground font-medium">Gen AI</span>
                      Thinking...
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <AssistantEmptyState
                title="Ask GenAI about this conversation."
                prompt="What would you like to know?"
                suggestions={quickQuestions}
              />
            )}
          </div>
        )}
      </div>
      {rightPanelTab === 'ai' && (
        <AssistantComposer
          className="mt-2"
          value={chatInput}
          onChange={setChatInput}
          onSubmit={(message) => sendAiMessage(message)}
          placeholder="Ask GenAI about this conversation..."
          busy={aiLoading}
        />
      )}
    </div>
  );
}
