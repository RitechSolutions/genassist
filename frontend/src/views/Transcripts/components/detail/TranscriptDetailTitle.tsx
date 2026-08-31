import { Check, MessageSquare, PlayCircle, Share2 } from 'lucide-react';
import type { ReactNode } from 'react';

import { Button } from '@/components/button';
import { cn } from '@/helpers/utils';
import type { TranscriptDetailController, TranscriptRightPanelTab } from '../../hooks/useTranscriptDetail';

type TranscriptDetailTitleProps = {
  controller: TranscriptDetailController;
  /** Rendered before the conversation icon — used by the workspace for its back button. */
  leading?: ReactNode;
  /** Rendered after the share button, e.g. the workspace's "toggle stats" control. */
  trailing?: ReactNode;
  className?: string;
};

const PANEL_OPTIONS: { value: TranscriptRightPanelTab; label: string }[] = [
  { value: 'transcript', label: 'Transcript' },
  { value: 'ai', label: 'Ask GenAI' },
];

/**
 * Switches the conversation column between the transcript and the assistant. Built from spans and
 * buttons rather than `Tabs` so it stays valid markup inside the dialog's `<h2>` title.
 */
function PanelSwitch({
  value,
  onChange,
}: {
  value: TranscriptRightPanelTab;
  onChange: (value: TranscriptRightPanelTab) => void;
}) {
  return (
    <span className="inline-flex shrink-0 items-center rounded-full bg-muted p-0.5 leading-normal text-muted-foreground">
      {PANEL_OPTIONS.map((option) => {
        const isActive = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={isActive}
            onClick={() => onChange(option.value)}
            className={cn(
              'whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              isActive ? 'bg-background text-foreground shadow-sm' : 'hover:text-foreground'
            )}
          >
            {option.label}
          </button>
        );
      })}
    </span>
  );
}

/**
 * The conversation title row (icon, id, supervisor chip, panel switch, share link) without any
 * dialog chrome, so it can sit inside a `DialogTitle` or straight in a page header.
 */
export function TranscriptDetailTitle({
  controller,
  leading,
  trailing,
  className,
}: TranscriptDetailTitleProps) {
  const {
    transcript,
    isCall,
    headerAgentName,
    supervisorId,
    supervisorDisplayName,
    linkCopied,
    copyShareLink,
    showAskGenAI,
    rightPanelTab,
    setActiveTab,
  } = controller;

  if (!transcript) return null;

  return (
    <span className={cn('flex w-full flex-col gap-1.5 items-start', className)}>
      <span className="flex w-full items-center gap-2">
        {leading}
        {isCall ? <PlayCircle className="w-5 h-5 shrink-0" /> : <MessageSquare className="w-5 h-5 shrink-0" />}
        <span className="truncate">
          {isCall ? 'Call' : 'Chat'} #{(transcript?.metadata?.title ?? '----').slice(-4)}
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
        <span className="ml-auto flex shrink-0 items-center gap-2">
          {/* Without the assistant there is nothing to switch between, so the control is dropped. */}
          {showAskGenAI && <PanelSwitch value={rightPanelTab} onChange={setActiveTab} />}
          <Button
            variant="ghost"
            size="sm"
            className={`h-7 w-7 p-0 transition-colors ${linkCopied ? 'text-green-600 dark:text-green-400' : ''}`}
            title="Copy share link"
            disabled={linkCopied}
            onClick={copyShareLink}
          >
            {linkCopied ? <Check className="h-4 w-4" /> : <Share2 className="h-4 w-4" />}
          </Button>
          {trailing}
        </span>
      </span>
      {headerAgentName ? (
        <span className="flex items-center gap-1.5 text-sm font-normal text-muted-foreground pr-10">
          {headerAgentName}
        </span>
      ) : null}
    </span>
  );
}
