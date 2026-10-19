import React from "react";
import { ChevronRight, Workflow as WorkflowIcon } from "lucide-react";
import FormattedText from "@/components/FormattedText";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/dialog";
import { cn } from "@/helpers/utils";
import type { RunConversationResult, RunTurnResult, Verdict } from "@/interfaces/testSuite.interface";
import {
  type CheckTally,
  type GradedItem,
  type QuestionResult,
  excerpt,
  ofThisReply,
  replyVerdict,
  tallyItems,
  turnGrading,
  verdictLabel,
} from "../helpers/runConversations";
import { GradedItemRow, VerdictIcon } from "./resultsParts";

const BUBBLE = "whitespace-pre-wrap break-words rounded-lg px-3 py-2 text-sm";
// A reply's buttons, set under it as pills.
export const PILL =
  "flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-0.5 text-xs font-medium transition-colors hover:bg-accent";

const Speaker: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className }) => (
  <span className={cn("mb-1 text-[11px] font-medium text-muted-foreground", className)}>{children}</span>
);

/** A message the run sent, as the customer's bubble. */
export const CustomerBubble: React.FC<{ message: string }> = ({ message }) => (
  <div className="flex flex-col items-start">
    <Speaker>Customer</Speaker>
    <div
      className={cn(
        BUBBLE,
        "max-w-[85%] rounded-tl-none bg-muted sm:max-w-[75%]",
        !message && "italic text-muted-foreground",
      )}
    >
      {message || "No message"}
    </div>
  </div>
);

const counted = (count: number, noun: string) => `${count} ${noun}`;

/** "2 passed, 1 failed", leaving out what did not happen. */
const tallyWords = (tally: CheckTally) =>
  [
    tally.passed && counted(tally.passed, "passed"),
    tally.failed && counted(tally.failed, "failed"),
    tally.notEvaluated && counted(tally.notEvaluated, "not evaluated"),
  ]
    .filter(Boolean)
    .join(", ");

/** Each verdict that happened, failed first, as its icon and count; filled for a turn's own checks. */
const TallyIcons: React.FC<{ tally: CheckTally; filled?: boolean }> = ({ tally, filled }) => (
  <>
    {(
      [
        ["failed", tally.failed],
        ["not_evaluated", tally.notEvaluated],
        ["passed", tally.passed],
      ] as [Verdict, number][]
    )
      .filter(([, count]) => count > 0)
      .map(([verdict, count]) => (
        <span key={verdict} className="inline-flex items-center gap-1 tabular-nums">
          <VerdictIcon verdict={verdict} filled={filled} className="h-3.5 w-3.5" />
          {count}
        </span>
      ))}
  </>
);

/** A turn's reply as the agent's bubble, and below it the steps and how its checks went. */
export const AgentReply: React.FC<{
  turn: RunTurnResult;
  conversation: RunConversationResult;
  /** Fills its column, as beside another run's reply; otherwise it sits on the right like a chat. */
  fill?: boolean;
  /** Who replied: the agent, or the run when two are side by side. */
  speaker?: string;
  onShowSteps?: () => void;
  /** Without it the checks pill is left out, as when one pill compares two runs' replies. */
  onShowChecks?: () => void;
}> = ({ turn, conversation, fill = false, speaker = "Agent", onShowSteps, onShowChecks }) => {
  const crashed = turn.status === "execution_failed";
  const skipped = turn.status === "skipped";
  // A turn that ran but could not be graded still replied.
  const reply = skipped || crashed ? null : turn.reply;
  const { items, questions } = turnGrading(turn, conversation);
  // Whole-conversation checks and the turn's own are counted apart, so they can look different.
  const whole = tallyItems(items.filter((item) => item.whole));
  const own = tallyItems(
    items.filter((item) => !item.whole),
    questions,
  );
  const summary = !onShowChecks
    ? ""
    : [own.total > 0 && `This turn: ${tallyWords(own)}`, whole.total > 0 && `Whole conversation: ${tallyWords(whole)}`]
        .filter(Boolean)
        .join(". ");
  const steps = turn.has_trace && onShowSteps;
  // Every reply has these buttons, so each names the message it answered.
  const about = `the reply to “${excerpt(turn.message || "No message", 40)}”`;

  return (
    <div className={cn("flex flex-col", fill ? "items-stretch" : "items-end")}>
      <Speaker>{speaker}</Speaker>
      {/* How it went shows in the checks pill below, so the bubble needs no icon of its own. */}
      <div className={cn("flex", fill ? "w-full" : "max-w-[85%] sm:max-w-[75%]")}>
        <div className={cn("flex min-w-0 flex-col", fill && "flex-1")}>
          <div
            className={cn(
              BUBBLE,
              "rounded-tr-none",
              reply
                ? "whitespace-normal bg-blue-600 text-white"
                : crashed
                  ? "border border-destructive/40 bg-destructive/5 italic text-destructive"
                  : "border border-dashed bg-background italic text-muted-foreground",
            )}
          >
            {/* Formatted as the chat shows it to the customer. */}
            {reply ? <FormattedText text={reply} /> : skipped ? "Did not run" : crashed ? "Did not finish" : "No reply"}
          </div>
          {(steps || summary || (crashed && turn.reason)) && (
            <div className="mt-1.5 flex flex-wrap items-center justify-end gap-1.5">
              {steps && (
                <button type="button" onClick={onShowSteps} aria-label={`Steps for ${about}`} className={PILL}>
                  <WorkflowIcon className="h-3.5 w-3.5 text-muted-foreground" />
                  Steps
                </button>
              )}
              {summary ? (
                <button
                  type="button"
                  onClick={onShowChecks}
                  title={summary}
                  aria-label={`${summary}. See details for ${about}`}
                  className={cn(PILL, "gap-2.5")}
                >
                  {own.total > 0 && (
                    <span className="flex items-center gap-2">
                      <TallyIcons tally={own} filled />
                    </span>
                  )}
                  {whole.total > 0 && own.total > 0 && <span aria-hidden="true" className="h-3 w-px bg-border" />}
                  {whole.total > 0 && (
                    <span className="flex items-center gap-2">
                      <TallyIcons tally={whole} />
                    </span>
                  )}
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                </button>
              ) : (
                crashed &&
                turn.reason &&
                onShowChecks && (
                  <button type="button" onClick={onShowChecks} className={cn(PILL, "text-destructive")}>
                    Why it did not finish
                  </button>
                )
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const STATUS_ORDER: Verdict[] = ["failed", "not_evaluated", "passed"];

/** A check on one reply: what happened on it, then the rule it was held to; a grader's reason stays under its rule. */
const ReplyCheckRow: React.FC<{ item: GradedItem }> = ({ item }) => {
  const fact = !item.graded && item.status !== "not_evaluated" && item.actual ? ofThisReply(item.actual) : null;
  // A turn's own check is about this reply; a whole-conversation one keeps its "every reply" or "no reply".
  const rule = item.whole ? item.title : ofThisReply(item.title);
  const lines = fact ? [rule, item.note] : [item.status === "not_evaluated" ? item.note : item.actual];
  return (
    <div className="flex items-start gap-2">
      <VerdictIcon verdict={item.status} filled={!item.whole} className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <p className="text-sm">{fact ?? rule}</p>
        {lines.filter(Boolean).map((line) => (
          <p key={line} className="mt-0.5 text-xs text-muted-foreground">
            {line}
          </p>
        ))}
      </div>
    </div>
  );
};

/** One kind of check, the turn's own or the whole conversation's: its icons in the heading, then a card each, failed first. */
const CheckSection: React.FC<{
  title: string;
  items: GradedItem[];
  questions?: QuestionResult[];
  filled?: boolean;
}> = ({ title, items, questions = [], filled }) => {
  if (!items.length && !questions.length) return null;
  const order = (status: Verdict) => STATUS_ORDER.indexOf(status);
  const cards = [...items].sort((a, b) => order(a.status) - order(b.status));
  // An older method sits under its question, failed questions first.
  const blocks = [...questions].sort((a, b) => order(a.status) - order(b.status));
  return (
    <section className="space-y-2">
      <h3 className="flex items-center gap-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
        <span className="flex items-center gap-2 font-medium normal-case tracking-normal text-foreground">
          <TallyIcons tally={tallyItems(items, questions)} filled={filled} />
        </span>
      </h3>
      {cards.map((item) => (
        <div key={item.key} className="rounded-lg border bg-card p-3">
          <ReplyCheckRow item={item} />
        </div>
      ))}
      {blocks.map((question) => (
        <div key={question.key} className="space-y-2 rounded-lg border bg-card p-3">
          <div className="flex items-center gap-2">
            <VerdictIcon verdict={question.status} filled={filled} />
            <span className="text-sm font-medium">{question.label}</span>
          </div>
          <div className="ml-6 space-y-2">
            {question.items.map((item) => (
              <GradedItemRow key={item.key} item={item} filled={filled} />
            ))}
          </div>
        </div>
      ))}
    </section>
  );
};

/** What was checked on one reply: the reply beside what was expected, then each check. */
export const TurnChecksDialog: React.FC<{
  turn: RunTurnResult;
  conversation: RunConversationResult;
  /** Names the run, when two are side by side. */
  runLabel?: string;
  onClose: () => void;
}> = ({ turn, conversation, runLabel, onClose }) => {
  const { items, questions } = turnGrading(turn, conversation);
  const crashed = turn.status === "execution_failed";
  const nothing = !items.length && !questions.length;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="flex max-h-[85vh] flex-col gap-0 overflow-hidden p-0 sm:max-w-2xl">
        <DialogHeader className="mb-0 shrink-0 space-y-1 border-b px-6 py-4 pr-12 text-left">
          <DialogTitle className="flex items-center gap-2">
            {/* One reply's result, so filled like its own checks. */}
            <VerdictIcon verdict={replyVerdict(turn, conversation)} className="h-5 w-5" filled />
            {verdictLabel(replyVerdict(turn, conversation))}
            {runLabel && <span className="font-normal text-muted-foreground">· {runLabel}</span>}
          </DialogTitle>
          <DialogDescription className="line-clamp-2">The reply to “{turn.message || "No message"}”</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-5">
          {turn.verdict !== "passed" && turn.reason && (
            <p
              className={cn(
                "rounded-lg border px-3 py-2 text-sm",
                crashed
                  ? "border-destructive/40 bg-destructive/5 text-destructive"
                  : "bg-muted/40 text-muted-foreground",
              )}
            >
              {turn.reason}
            </p>
          )}
          {nothing ? (
            <p className="text-sm text-muted-foreground">Nothing checked this reply.</p>
          ) : (
            <div className="space-y-6">
              <CheckSection
                title="This turn"
                items={items.filter((item) => !item.whole)}
                questions={questions}
                filled
              />
              <CheckSection title="Whole conversation" items={items.filter((item) => item.whole)} />
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
