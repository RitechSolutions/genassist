import { Coins, Megaphone, Pencil, ThumbsDown, ThumbsUp } from 'lucide-react';

import { Button } from '@/components/button';
import { Switch } from '@/components/switch';
import { Tabs, TabsList, TabsTrigger } from '@/components/tabs';
import { Textarea } from '@/components/ui/textarea';
import { formatFeedbackDate } from '@/helpers/utils';
import { cn } from '@/helpers/utils';

import { getEffectiveSentiment } from '../../helpers/formatting';
import type { TranscriptDetailController, TranscriptLeftPanelTab } from '../../hooks/useTranscriptDetail';
import { MetricCards } from '../MetricCard';
import { ScoreCards } from '../ScoreCard';
import { TranscriptAudioPlayer } from '../TranscriptAudioPlayer';

type TranscriptStatsPanelProps = {
  controller: TranscriptDetailController;
  className?: string;
};

/**
 * Stats / Feedback / Costs for a finalized conversation. Extracted from `TranscriptDialog`
 * so the Conversations workspace can render it as its own column.
 */
export function TranscriptStatsPanel({ controller, className }: TranscriptStatsPanelProps) {
  const {
    transcript,
    isCall,
    audioSrc,
    audioLoading,
    leftPanelTab,
    setLeftPanelTab,
    showCosts,
    setShowCosts,
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
  } = controller;

  if (!transcript) return null;

  return (
    <div className={cn('space-y-4 flex flex-col', className)}>
      {/* Left Panel Toggle */}
      <Tabs
        value={leftPanelTab}
        onValueChange={(value) => setLeftPanelTab(value as TranscriptLeftPanelTab)}
        className="w-full"
      >
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="stats">Stats</TabsTrigger>
          <TabsTrigger value="feedback">Feedback</TabsTrigger>
          <TabsTrigger value="costs">Costs</TabsTrigger>
        </TabsList>
      </Tabs>

      <MetricCards
        duration={Number(transcript.duration)}
        wordCount={transcript.metrics.wordCount}
        sentiment={getEffectiveSentiment(transcript)}
        speakingRatio={transcript.metrics.speakingRatio}
      />

      {leftPanelTab === 'stats' && (
        <>
          <div className="flex items-center gap-2 px-2 justify-between">
            <div className="flex flex-row items-center gap-2">
              <Megaphone className="w-4 h-4 text-yellow-500" />
              <span className="text-sm font-medium"> Conversation Tone</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {transcript.metrics.tone.map((tone, index) => (
                <span key={index} className="px-2 py-1 bg-muted text-foreground rounded-full text-xs font-bold">
                  {tone.toLowerCase()}
                </span>
              ))}
            </div>
          </div>

          {isCall && <TranscriptAudioPlayer isLoading={audioLoading} audioSrc={audioSrc} />}

          <ScoreCards metrics={transcript.metrics} />
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

              <Button onClick={startEditFeedback} variant="outline" className="w-full text-sm flex items-center gap-2">
                <Pencil className="w-4 h-4" />
                Edit Feedback
              </Button>
            </div>
          ) : (
            // Input form for editing feedback
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
                  onClick={submitFeedback}
                  disabled={!feedbackType || feedbackSubmitting}
                  className="flex-1 bg-blue-600 text-white hover:bg-blue-700"
                >
                  {feedbackSubmitting ? 'Submitting...' : 'Save'}
                </Button>

                {isEditing && (
                  <Button onClick={cancelEditFeedback} variant="outline" className="px-4">
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
            <p className="text-sm text-muted-foreground flex justify-between">
              <span>Input Tokens:</span> <b>{totalCost.input_tokens}</b>
            </p>
            <p className="text-sm text-muted-foreground flex justify-between">
              <span>Output Tokens:</span> <b>{totalCost.output_tokens}</b>
            </p>
            <p className="text-sm text-muted-foreground flex justify-between">
              <span>Total Cost:</span> <b>${totalCost.total.toFixed(6)}</b>
            </p>
          </div>
        </>
      )}
    </div>
  );
}
