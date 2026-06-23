import { ComponentType, ReactNode } from "react";
import {
  Flag,
  Quote,
  MessageCircle,
  Workflow,
  Clock,
  User,
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
import { formatDate } from "../constants";
import { StatusSelect } from "./StatusSelect";

type ReportedFeedbackDialogProps = {
  issue: ReportedFeedbackItem | null;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onStatusChange: (issue: ReportedFeedbackItem, next: FeedbackStatus) => void;
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
  if (!issue) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl gap-0 overflow-hidden p-0">
        <DialogHeader className="space-y-0 border-b px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-600">
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

        <div className="max-h-[65vh] space-y-5 overflow-y-auto px-6 py-5">
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

          <section className="grid grid-cols-1 gap-x-6 gap-y-4 border-t pt-5 sm:grid-cols-2">
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
              value={formatDate(issue.reported_at)}
            />
            <Meta
              icon={MessageCircle}
              label="Conversation"
              value={`${issue.conversation_topic || "Untitled"} · ${formatDate(
                issue.conversation_date,
              )}`}
            />
          </section>
        </div>

        <div className="flex flex-wrap justify-end gap-2 border-t bg-muted/30 px-6 py-4">
          <Button
            type="button"
            variant="outline"
            className="rounded-full"
            disabled={!issue.agent_id}
            title={
              issue.agent_id
                ? "Open the agent's workflow"
                : "No workflow linked to this conversation"
            }
            onClick={() => onOpenWorkflow(issue.agent_id)}
          >
            <Workflow className="h-4 w-4" /> Go to workflow
          </Button>
          <Button
            type="button"
            className="rounded-full"
            onClick={() => onOpenConversation(issue.conversation_id)}
          >
            <MessageCircle className="h-4 w-4" /> Open conversation
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
