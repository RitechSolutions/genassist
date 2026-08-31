import { BotMessageSquare } from 'lucide-react';

import { Button } from '@/components/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/tabs';
import { Input } from '@/components/ui/input';
import { cn } from '@/helpers/utils';

import type { TranscriptDetailController, TranscriptRightPanelTab } from '../../hooks/useTranscriptDetail';
import { TranscriptThread } from '../TranscriptThread';

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
 * Transcript / Ask GenAI for a finalized conversation. Extracted from `TranscriptDialog`
 * so the Conversations workspace can render it as its own column.
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
    setActiveTab,
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

  const threadHeight = fill
    ? 'flex-1 min-h-0'
    : isCall
      ? 'h-[550px] 2xl:h-[min(70vh,660px)] min-[1920px]:h-[min(72vh,780px)]'
      : 'h-[460px] 2xl:h-[min(64vh,560px)] min-[1920px]:h-[min(68vh,680px)]';

  const aiHeight = fill
    ? 'flex-1 min-h-0'
    : isCall
      ? 'h-[500px] 2xl:h-[min(64vh,600px)] min-[1920px]:h-[min(66vh,720px)]'
      : 'h-[400px] 2xl:h-[min(58vh,500px)] min-[1920px]:h-[min(62vh,620px)]';

  return (
    <div className={cn('flex flex-col', fill && 'h-full min-h-0', className)}>
      <Tabs
        value={rightPanelTab}
        onValueChange={(value) => setActiveTab(value as TranscriptRightPanelTab)}
        className="pb-1"
      >
        <TabsList className={`grid w-full ${showAskGenAI ? 'grid-cols-2' : 'grid-cols-1'}`}>
          <TabsTrigger value="transcript">Transcript</TabsTrigger>
          {showAskGenAI && <TabsTrigger value="ai">Ask GenAI</TabsTrigger>}
        </TabsList>
      </Tabs>
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
            onKeyDown={(e) => e.key === 'Enter' && sendAiMessage()}
          />
          <Button onClick={sendAiMessage} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white">
            Send
          </Button>
        </div>
      )}
    </div>
  );
}
