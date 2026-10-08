import { ComponentType, ReactNode, useEffect, useState } from "react";
import { format, parseISO } from "date-fns";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  Flag,
  Quote,
  MessageCircle,
  Workflow,
  Clock,
  User,
  ChevronLeft,
  PanelRightClose,
  Wrench,
  CalendarDays,
  Tag,
  NotebookPen,
  Bug,
  X,
} from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/label";
import { Calendar } from "@/components/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import { AgentResponseLogDialog } from "@/components/AgentResponseLogDialog";
import { TruncatedText } from "@/components/TruncatedText";

import {
  addIssueNote,
  FeedbackStatus,
  fetchIssueNotes,
  IssuePatch,
  ReportedFeedbackItem,
} from "@/services/reportedFeedback";
import { IssueStatus } from "@/services/issueStatuses";
import { extractErrorMessage } from "@/helpers/apiError";
import { cn, formatDateTime } from "@/helpers/utils";
import {
  draftToPatch,
  formatDateOnly,
  isDraftDirty,
  toDateOnly,
  toDraft,
  topicLabel,
  TriageDraft,
} from "../helpers/triageDraft";
import { StatusBadge, StatusSelect } from "./StatusSelect";
import { ConversationPanel } from "./ConversationPanel";

type ReportedFeedbackDialogProps = {
  issue: ReportedFeedbackItem | null;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  statuses: IssueStatus[];
  canTriage: boolean;
  onStatusChange: (issue: ReportedFeedbackItem, next: FeedbackStatus) => void;
  /** Saves a partial update; resolves to the saved issue, or null after a failure it already reported. */
  onIssuePatch: (
    issue: ReportedFeedbackItem,
    patch: IssuePatch,
  ) => Promise<ReportedFeedbackItem | null>;
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
  statuses,
  canTriage,
  onStatusChange,
  onIssuePatch,
  onOpenConversation,
  onOpenWorkflow,
}: ReportedFeedbackDialogProps) {
  const queryClient = useQueryClient();
  // The conversation expands the dialog in place rather than navigating, so reviewers
  // keep their page, filters and scroll position in the list behind it.
  const [showConversation, setShowConversation] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [draft, setDraft] = useState<TriageDraft>(() =>
    toDraft(issue ?? { fix_version: null, target_rollout_date: null }),
  );
  const [savingTriage, setSavingTriage] = useState(false);
  const [noteDraft, setNoteDraft] = useState("");

  const issueId = issue?.feedback_id;
  useEffect(() => {
    setShowConversation(false);
    setDebugOpen(false);
    setNoteDraft("");
    if (issue) setDraft(toDraft(issue));
  }, [issueId]);

  const {
    data: notes = [],
    isLoading: notesLoading,
    isError: notesError,
  } = useQuery({
    queryKey: ["reported-feedback", "notes", issueId],
    queryFn: () => fetchIssueNotes(issueId as string),
    enabled: isOpen && Boolean(issueId),
  });

  const addNote = useMutation({
    mutationFn: (vars: { feedbackId: string; body: string }) =>
      addIssueNote(vars.feedbackId, vars.body),
    onSuccess: (_note, vars) => {
      setNoteDraft((current) => (current.trim() === vars.body ? "" : current));
      void queryClient.invalidateQueries({
        queryKey: ["reported-feedback", "notes", vars.feedbackId],
      });
      toast.success("Note added");
    },
    onError: (err) => toast.error(extractErrorMessage(err, "Failed to add note")),
  });

  if (!issue) return null;

  const canOpenConversation = Boolean(issue.conversation_id);
  const isAgentMessage = ["Agent", "agent"].includes(issue.speaker);
  const triageDirty = isDraftDirty(issue, draft);

  const saveTriage = async () => {
    const submitted = draft;
    setSavingTriage(true);
    const saved = await onIssuePatch(issue, draftToPatch(issue, draft));
    setSavingTriage(false);
    if (!saved) return;
    setDraft((current) => (current === submitted ? toDraft(saved) : current));
    toast.success("Triage saved");
  };

  const submitNote = () => {
    const body = noteDraft.trim();
    if (!body || addNote.isPending) return;
    addNote.mutate({ feedbackId: issue.feedback_id, body });
  };

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
              {canTriage ? (
                <StatusSelect
                  value={issue.status}
                  statuses={statuses}
                  onChange={(next) => onStatusChange(issue, next)}
                />
              ) : (
                <StatusBadge value={issue.status} statuses={statuses} />
              )}
            </div>

            {canTriage && (
              <section>
                <SectionLabel icon={Wrench}>Triage</SectionLabel>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="feedback-fix-version" className="text-xs">
                      Fix version
                    </Label>
                    <Input
                      id="feedback-fix-version"
                      className="h-9"
                      maxLength={100}
                      placeholder="e.g. 2.4.1"
                      value={draft.fix_version}
                      onChange={(e) =>
                        setDraft((current) => ({
                          ...current,
                          fix_version: e.target.value,
                        }))
                      }
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs">Target rollout date</Label>
                    <div className="flex items-center gap-1">
                      <Popover>
                        <PopoverTrigger asChild>
                          <Button
                            type="button"
                            variant="outline"
                            className="h-9 flex-1 justify-start gap-2 rounded-full font-normal"
                          >
                            <CalendarDays className="h-4 w-4 text-muted-foreground" />
                            {draft.target_rollout_date ? (
                              formatDateOnly(draft.target_rollout_date)
                            ) : (
                              <span className="text-muted-foreground">
                                Pick a date
                              </span>
                            )}
                          </Button>
                        </PopoverTrigger>
                        {/* Above DialogContent (z-[1300]). */}
                        <PopoverContent
                          className="z-[1400] w-auto p-0"
                          align="start"
                        >
                          <Calendar
                            mode="single"
                            required
                            selected={
                              draft.target_rollout_date
                                ? parseISO(draft.target_rollout_date)
                                : undefined
                            }
                            defaultMonth={
                              draft.target_rollout_date
                                ? parseISO(draft.target_rollout_date)
                                : undefined
                            }
                            onSelect={(day) =>
                              setDraft((current) => ({
                                ...current,
                                target_rollout_date: day
                                  ? toDateOnly(day)
                                  : null,
                              }))
                            }
                            initialFocus
                          />
                        </PopoverContent>
                      </Popover>
                      {draft.target_rollout_date && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-9 w-9 shrink-0 rounded-full"
                          title="Clear the target rollout date"
                          aria-label="Clear the target rollout date"
                          onClick={() =>
                            setDraft((current) => ({
                              ...current,
                              target_rollout_date: null,
                            }))
                          }
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
                <div className="mt-3 flex justify-end">
                  <Button
                    type="button"
                    size="sm"
                    className="rounded-full"
                    disabled={!triageDirty || savingTriage}
                    onClick={saveTriage}
                  >
                    {savingTriage ? "Saving..." : "Save"}
                  </Button>
                </div>
              </section>
            )}

            <section>
              <SectionLabel icon={NotebookPen}>Notes</SectionLabel>
              {notesLoading ? (
                <p className="text-sm text-muted-foreground">Loading notes...</p>
              ) : notesError ? (
                <p className="text-sm text-red-600 dark:text-red-400">
                  Couldn't load the notes.
                </p>
              ) : notes.length === 0 ? (
                <p className="text-sm text-muted-foreground">No notes yet</p>
              ) : (
                <ol className="space-y-2">
                  {notes.map((note) => (
                    <li key={note.id} className="rounded-lg border bg-muted/40 p-3">
                      <div className="mb-1 text-xs text-muted-foreground">
                        <span className="font-medium text-foreground">
                          {note.author_username ?? "Unknown user"}
                        </span>
                        {" · "}
                        {format(parseISO(note.created_at), "d MMM yyyy HH:mm")}
                      </div>
                      <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                        {note.body}
                      </div>
                    </li>
                  ))}
                </ol>
              )}
              {canTriage && (
                <div className="mt-3 space-y-2">
                  <Textarea
                    rows={2}
                    maxLength={5000}
                    placeholder="Add a note about what was changed and how"
                    aria-label="New note"
                    value={noteDraft}
                    onChange={(e) => setNoteDraft(e.target.value)}
                  />
                  <div className="flex justify-end">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="rounded-full"
                      disabled={!noteDraft.trim() || addNote.isPending}
                      onClick={submitNote}
                    >
                      {addNote.isPending ? "Adding..." : "Add note"}
                    </Button>
                  </div>
                </div>
              )}
            </section>

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
                label="AI topic"
                value={
                  <TruncatedText>
                    {`${
                      issue.conversation_topic
                        ? topicLabel(issue.conversation_topic, issue.conversation_subtopic)
                        : "Untitled"
                    } · ${formatDateTime(issue.conversation_date)}`}
                  </TruncatedText>
                }
              />
              {issue.target_rollout_date && (
                <Meta
                  icon={CalendarDays}
                  label="Target rollout"
                  value={formatDateOnly(issue.target_rollout_date)}
                />
              )}
              {issue.fix_version && (
                <Meta icon={Tag} label="Fix version" value={issue.fix_version} />
              )}
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
            disabled={!isAgentMessage}
            title={
              isAgentMessage
                ? "Show the agent's response log for this message"
                : "Only agent replies have a response log"
            }
            onClick={() => setDebugOpen(true)}
          >
            <Bug className="h-4 w-4" /> Debug response
          </Button>
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

        <AgentResponseLogDialog
          isOpen={debugOpen}
          onOpenChange={setDebugOpen}
          messageId={issue.message_id}
        />
      </DialogContent>
    </Dialog>
  );
}
