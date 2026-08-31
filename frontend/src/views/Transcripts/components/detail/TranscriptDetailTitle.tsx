import { Check, MessageSquare, PlayCircle, Share2 } from 'lucide-react';
import type { ReactNode } from 'react';

import { Button } from '@/components/button';
import { cn } from '@/helpers/utils';
import type { TranscriptDetailController } from '../../hooks/useTranscriptDetail';

type TranscriptDetailTitleProps = {
  controller: TranscriptDetailController;
  /** Rendered before the conversation icon — used by the workspace for its back button. */
  leading?: ReactNode;
  /** Rendered after the share button, e.g. the workspace's "toggle stats" control. */
  trailing?: ReactNode;
  className?: string;
};

/**
 * The conversation title row (icon, id, supervisor chip, share link) without any dialog
 * chrome, so it can sit inside a `DialogTitle` or straight in a page header.
 */
export function TranscriptDetailTitle({
  controller,
  leading,
  trailing,
  className,
}: TranscriptDetailTitleProps) {
  const { transcript, isCall, headerAgentName, supervisorId, supervisorDisplayName, linkCopied, copyShareLink } =
    controller;

  if (!transcript) return null;

  return (
    <span className={cn('flex w-full flex-col gap-1.5 items-start', className)}>
      <span className="flex w-full items-center gap-2">
        {leading}
        {isCall ? <PlayCircle className="w-5 h-5 shrink-0" /> : <MessageSquare className="w-5 h-5 shrink-0" />}
        <span>
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
        <Button
          variant="ghost"
          size="sm"
          className={`ml-auto h-7 w-7 p-0 transition-colors ${linkCopied ? 'text-green-600 dark:text-green-400' : ''}`}
          title="Copy share link"
          disabled={linkCopied}
          onClick={copyShareLink}
        >
          {linkCopied ? <Check className="h-4 w-4" /> : <Share2 className="h-4 w-4" />}
        </Button>
        {trailing}
      </span>
      {headerAgentName ? (
        <span className="flex items-center gap-1.5 text-sm font-normal text-muted-foreground pr-10">
          {headerAgentName}
        </span>
      ) : null}
    </span>
  );
}
