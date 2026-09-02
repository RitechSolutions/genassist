import { ComponentType, ReactNode, useEffect, useState } from "react";
import {
  Flag,
  Quote,
  MessageCircle,
  Workflow,
  Clock,
  User,
  ChevronLeft,
  PanelRightClose,
} from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Button } from "@/components/button";

import {
  FeedbackStatus,
  ReportedFeedbackItem,
} from "@/services/reportedFeedback";
import { cn, formatDateTime } from "@/helpers/utils";
import { StatusSelect } from "./StatusSelect";
import { ConversationPanel } from "./ConversationPanel";

type ReportedFeedbackDialogProps = {
  issue: ReportedFeedbackItem | null;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onStatusChange: (issue: ReportedFeedbackItem, next: FeedbackStatus) => void;
  /** Escape hatch to the full Transcripts view — the dialog embeds the thread itself. */
  onOpenConversation: (conversationId: string) => void;
  onOpenWorkflow: (agentId: string | null) => void;
};

function SectionLabel({
  icon: Icon,
  children,
}: {
  icon: ComponentType<{ className?: string }>;
  children: ReactNode;
}) {
  return (
    <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
      <Icon className="h-3.5 w-3.5" />
      {children}
    </div>
  );
}

function Meta({
  icon: Icon,
  label,
  value,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="flex items-start gap-2.5">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
      </div>
      <div className="min-w-0">
        <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </div>
        <div className="truncate text-sm text-foreground">{value}</div>
      </div>
    </div>
  );
}

export function ReportedFeedbackDialog({
  issue,
  isOpen,
  onOpenChange,
  onStatusChange,
  onOpenConversation,
  onOpenWorkflow,
}: ReportedFeedbackDialogProps) {
  // The conversation expands the dialog in place rather than navigating, so reviewers
  // keep their page, filters and scroll position in the list behind it.
  const [showConversation, setShowConversation] = useState(false);

  const issueId = issue?.feedback_id;
  useEffect(() => {
    setShowConversation(false);
  }, [issueId]);

  if (!issue) return null;

  const canOpenConversation = Boolean(issue.conversation_id);

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          "flex flex-col gap-0 overflow-hidden p-0 transition-[max-width] duration-300 ease-out",
          showConversation ? "h-[85vh] max-w-6xl" : "max-w-2xl",
        )}
      >
        <DialogHeader className="shrink-0 space-y-0 border-b px-6 py-4">
          <div className="flex items-center gap-3">
            {showConversation && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="-ml-2 h-8 w-8 shrink-0 p-0"
                title="Back to feedback details"
                aria-label="Back to feedback details"
                onClick={() => setShowConversation(false)}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
            )}
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400">
              <Flag className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <DialogTitle className="text-base">Reported Feedback</DialogTitle>
              <p className="font-mono text-xs text-muted-foreground">
                Conversation #{(issue.conversation_id || "----").slice(-4)}
              </p>
            </div>
          </div>
        </DialogHeader>

        <div
          className={cn(
            "min-h-0",
            showConversation
              ? "grid flex-1 grid-cols-1 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]"
              : "flex flex-col",
          )}
        >
          {/* Detail pane. Hidden on narrow screens once the conversation is showing —
              the header's back control brings it back. */}
          <div
            className={cn(
              "min-h-0 space-y-5 overflow-y-auto px-6 py-5",
              showConversation
                ? "hidden lg:block lg:border-r"
                : "max-h-[65vh]",
            )}
          >
            <div className="flex items-center justify-between gap-3">
              <SectionLabel icon={Flag}>Status</SectionLabel>
              <StatusSelect
                value={issue.status}
                onChange={(next) => onStatusChange(issue, next)}
              />
            </div>

            <section>
              <SectionLabel icon={Quote}>Comment</SectionLabel>
              <div className="rounded-lg border bg-muted/40 p-3 text-sm leading-relaxed whitespace-pre-wrap break-words">
                {issue.comment}
              </div>
            </section>

            <section>
              <SectionLabel icon={MessageCircle}>
                Flagged message · {issue.speaker}
              </SectionLabel>
              <div className="max-h-48 overflow-y-auto rounded-lg border bg-background p-3 text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap break-words">
                {issue.text}
              </div>
            </section>

            <section
              className={cn(
                "grid grid-cols-1 gap-x-6 gap-y-4 border-t pt-5",
                !showConversation && "sm:grid-cols-2",
              )}
            >
              <Meta
                icon={Workflow}
                label="Workflow"
                value={issue.workflow_name || "—"}
              />
              <Meta
                icon={User}
                label="Reported by"
                value={issue.reported_by ?? "—"}
              />
              <Meta
                icon={Clock}
                label="Reported at"
                value={formatDateTime(issue.reported_at)}
              />
              <Meta
                icon={MessageCircle}
                label="Conversation"
                value={`${issue.conversation_topic || "Untitled"} · ${formatDateTime(
                  issue.conversation_date,
                )}`}
              />
            </section>
          </div>

          {showConversation && canOpenConversation && (
            <ConversationPanel
              key={issue.conversation_id}
              conversationId={issue.conversation_id}
              highlightMessageId={issue.message_id}
              topic={issue.conversation_topic}
              conversationDate={issue.conversation_date}
              onOpenFullTranscript={() =>
                onOpenConversation(issue.conversation_id)
              }
            />
          )}
        </div>

        <div className="flex shrink-0 flex-wrap justify-end gap-2 border-t bg-muted/30 px-6 py-4">
          <Button
            type="button"
            variant="outline"
            className="rounded-full"
            disabled={!issue.agent_id}
            title={
              issue.agent_id
                ? "Open the agent's workflow in a new tab"
                : "No workflow linked to this conversation"
            }
            onClick={() => onOpenWorkflow(issue.agent_id)}
          >
            <Workflow className="h-4 w-4" /> Go to workflow
          </Button>
          <Button
            type="button"
            className="rounded-full"
            disabled={!canOpenConversation}
            title={
              canOpenConversation
                ? showConversation
                  ? "Collapse the conversation"
                  : "Read the conversation without leaving this page"
                : "No conversation linked to this feedback"
            }
            onClick={() => setShowConversation((current) => !current)}
          >
            {showConversation ? (
              <>
                <PanelRightClose className="h-4 w-4" /> Hide conversation
              </>
            ) : (
              <>
                <MessageCircle className="h-4 w-4" /> Open conversation
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
