import React, { useState } from "react";
import { AlertTriangle, ArrowUp, Check, CircleHelp, Pencil, Sparkles, Undo2, Wrench, Play } from "lucide-react";
import { Button } from "@/components/button";
import { cn } from "@/helpers/utils";
import type { AssistProposal, BuilderQuestion, ReviewFinding } from "@/services/workflowBuilder";
import type { PendingChange } from "@/views/AIAgents/Workflows/hooks/useCanvasAssistant";
import { FIX_ISSUES_MESSAGE, type AssistantMessage } from "@/views/AIAgents/Workflows/utils/assistantDraft";

const SEVERITY = {
  error: "bg-red-50 text-red-700 border-red-200 dark:bg-red-500/15 dark:text-red-400 dark:border-red-500/30",
  warning: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/15 dark:text-amber-400 dark:border-amber-500/30",
  setup: "bg-muted text-muted-foreground border-border",
};

interface Props {
  msg: AssistantMessage;
  /** True for the newest message, where action buttons make sense. */
  isLatest: boolean;
  busy: boolean;
  onSend: (message: string, focusNodeIds?: string[]) => void;
  onApplyProposal?: (messageId: string, proposal: AssistProposal) => void;
  onRunSuggestedTest?: (message: string) => void;
  /** Centre the canvas on a node and open its settings (for issues and findings). */
  onFocusNode?: (nodeId: string, openSettings: boolean) => void;
  /** Answer the question the assistant asked in this message. */
  onAnswer?: (messageId: string, answer: string) => void;
}

/**
 * Everything an assistant message can carry besides its text: a question to
 * answer, the issues it left (with a one-click fix), proposals waiting for
 * approval, suggested test messages, and review findings. (What it changed is
 * listed under the "Worked for…" line above the text.)
 */
export const AssistantMessageExtras: React.FC<Props> = ({
  msg,
  isLatest,
  busy,
  onSend,
  onApplyProposal,
  onRunSuggestedTest,
  onFocusNode,
  onAnswer,
}) => {
  const issues = msg.issues ?? [];
  const findings: ReviewFinding[] = msg.findings ?? [];
  return (
    <>
      {msg.question && (
        <QuestionCard
          question={msg.question}
          answer={msg.answer}
          disabled={busy || !isLatest || !onAnswer}
          onAnswer={(answer) => onAnswer?.(msg.id, answer)}
        />
      )}

      {issues.length > 0 && (
        <ul className="mt-2 space-y-1">
          {issues.map((issue, index) => (
            <li
              key={`${issue.code}-${index}`}
              className={`flex items-start gap-1.5 text-xs rounded-md border px-2.5 py-1.5 ${SEVERITY[issue.severity]}`}
            >
              <AlertTriangle className="h-3 w-3 mt-0.5 flex-shrink-0" />
              {issue.node_id && onFocusNode ? (
                <button
                  type="button"
                  className="text-left underline-offset-2 hover:underline"
                  onClick={() => onFocusNode(issue.node_id as string, issue.severity === "setup")}
                >
                  {issue.message}
                </button>
              ) : (
                <span>{issue.message}</span>
              )}
            </li>
          ))}
          {isLatest && !busy && issues.some((issue) => issue.severity === "error") && (
            <li>
              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => onSend(FIX_ISSUES_MESSAGE)}>
                Fix these
              </Button>
            </li>
          )}
        </ul>
      )}

      {msg.proposals && msg.proposals.length > 0 && (
        <ul className="mt-2 space-y-2">
          {msg.proposals.map((proposal, index) => (
            <li key={`${proposal.title}-${index}`} className="rounded-md border border-border bg-muted/40 px-3 py-2">
              <div className="text-xs font-medium text-foreground">{proposal.title}</div>
              {proposal.why && <div className="mt-0.5 text-xs text-muted-foreground">{proposal.why}</div>}
              {proposal.operations.length === 1 &&
                typeof proposal.operations[0].value === "string" && (
                  <pre className="mt-1.5 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-background p-2 text-[11px] leading-4 text-foreground">
                    {String(proposal.operations[0].value)}
                  </pre>
                )}
              <div className="mt-2 flex gap-2">
                <Button
                  size="sm"
                  className="h-7 text-xs"
                  disabled={busy || !onApplyProposal}
                  onClick={() => onApplyProposal?.(msg.id, proposal)}
                >
                  <Check className="mr-1 h-3 w-3" />
                  Apply
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {msg.suggestions && msg.suggestions.length > 0 && (
        <ul className="mt-2 space-y-1">
          {msg.suggestions.map((suggestion, index) => (
            <li key={index}>
              <button
                type="button"
                disabled={!onRunSuggestedTest}
                onClick={() => onRunSuggestedTest?.(suggestion)}
                className="flex w-full items-start gap-1.5 rounded-md border border-border bg-muted/40 px-2.5 py-1.5 text-left text-xs hover:bg-muted disabled:cursor-default"
              >
                <Play className="mt-0.5 h-3 w-3 flex-shrink-0 text-[hsl(var(--brand-600))]" />
                <span>{suggestion}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {findings.length > 0 && (
        <ul className="mt-2 space-y-1">
          {findings.map((finding, index) => (
            <li
              key={`${finding.code}-${index}`}
              className={`flex items-start gap-1.5 text-xs rounded-md border px-2.5 py-1.5 ${SEVERITY[finding.severity]}`}
            >
              <AlertTriangle className="h-3 w-3 mt-0.5 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                {finding.node_id && onFocusNode ? (
                  <button
                    type="button"
                    className="text-left underline-offset-2 hover:underline"
                    onClick={() => onFocusNode(finding.node_id as string, finding.severity === "setup")}
                  >
                    {finding.message}
                  </button>
                ) : (
                  <span>{finding.message}</span>
                )}
              </div>
              {finding.fix && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onSend(finding.fix as string, finding.node_id ? [finding.node_id] : [])}
                  className="inline-flex shrink-0 items-center gap-1 rounded border border-current/30 px-1.5 py-0.5 text-[11px] hover:bg-background/60"
                >
                  <Wrench className="h-3 w-3" />
                  Fix
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  );
};

/**
 * A question from the assistant with its answers as buttons: the one it would
 * pick first, marked, plus "Something else" for the person's own words. Once
 * answered it stays as a record of what was chosen.
 */
export const QuestionCard: React.FC<{
  question: BuilderQuestion;
  answer?: string;
  disabled: boolean;
  onAnswer: (answer: string) => void;
}> = ({ question, answer, disabled, onAnswer }) => {
  const [other, setOther] = useState(false);
  const [custom, setCustom] = useState("");
  const options = [
    ...question.options.filter((option) => option === question.recommended),
    ...question.options.filter((option) => option !== question.recommended),
  ];
  const answered = Boolean(answer);
  const submitCustom = () => {
    if (!custom.trim()) return;
    onAnswer(custom.trim());
    setCustom("");
    setOther(false);
  };
  return (
    <div className="mt-2 overflow-hidden rounded-xl border border-border bg-muted/30">
      <div className="flex items-start gap-2 px-3 pt-2.5">
        <CircleHelp className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[hsl(var(--brand-600))]" aria-hidden />
        <p className="text-xs font-medium text-foreground">{question.question}</p>
      </div>
      <ul className="mt-2 space-y-1 px-2 pb-2">
        {options.map((option) => {
          const recommended = option === question.recommended;
          const chosen = answered && answer === option;
          return (
            <li key={option}>
              <button
                type="button"
                disabled={disabled || answered}
                onClick={() => onAnswer(option)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-lg border px-2.5 py-1.5 text-left text-xs transition-colors",
                  chosen
                    ? "border-[hsl(var(--brand-600))]/50 bg-[hsl(var(--brand-600))]/10 text-foreground"
                    : answered
                    ? "border-transparent text-muted-foreground opacity-60"
                    : "border-border bg-background text-foreground hover:border-[hsl(var(--brand-600))]/50 hover:bg-[hsl(var(--brand-600))]/5 disabled:cursor-default disabled:opacity-60"
                )}
              >
                <span
                  className={cn(
                    "flex h-4 w-4 shrink-0 items-center justify-center rounded-full border",
                    chosen ? "border-[hsl(var(--brand-600))] bg-[hsl(var(--brand-600))] text-white" : "border-border"
                  )}
                >
                  {chosen && <Check className="h-2.5 w-2.5" />}
                </span>
                <span className="min-w-0 flex-1">{option}</span>
                {recommended && !answered && (
                  <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-[hsl(var(--brand-600))]/10 px-1.5 py-0.5 text-[10px] font-medium text-[hsl(var(--brand-600))]">
                    <Sparkles className="h-2.5 w-2.5" />
                    Recommended
                  </span>
                )}
              </button>
            </li>
          );
        })}
        {answered && !question.options.includes(answer as string) && (
          <li className="flex items-center gap-2 rounded-lg border border-[hsl(var(--brand-600))]/50 bg-[hsl(var(--brand-600))]/10 px-2.5 py-1.5 text-xs text-foreground">
            <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-[hsl(var(--brand-600))] bg-[hsl(var(--brand-600))] text-white">
              <Check className="h-2.5 w-2.5" />
            </span>
            <span className="min-w-0 flex-1">{answer}</span>
          </li>
        )}
        {!answered && !other && (
          <li>
            <button
              type="button"
              disabled={disabled}
              onClick={() => setOther(true)}
              className="flex w-full items-center gap-2 rounded-lg border border-dashed border-border px-2.5 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:border-[hsl(var(--brand-600))]/50 hover:text-foreground disabled:cursor-default disabled:opacity-60"
            >
              <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-dashed border-border">
                <Pencil className="h-2.5 w-2.5" />
              </span>
              Something else…
            </button>
          </li>
        )}
        {!answered && other && (
          <li className="flex items-center gap-1.5 rounded-lg border border-[hsl(var(--brand-600))]/50 bg-background py-1 pl-2.5 pr-1 text-xs">
            <input
              autoFocus
              value={custom}
              disabled={disabled}
              onChange={(event) => setCustom(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  submitCustom();
                }
                if (event.key === "Escape") setOther(false);
              }}
              placeholder="Type your answer…"
              aria-label="Your answer"
              className="min-w-0 flex-1 bg-transparent text-xs text-foreground placeholder:text-muted-foreground focus:outline-none"
            />
            <button
              type="button"
              onClick={submitCustom}
              disabled={disabled || !custom.trim()}
              aria-label="Send answer"
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[hsl(var(--brand-600))] text-white transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              <ArrowUp className="h-3 w-3" />
            </button>
          </li>
        )}
      </ul>
    </div>
  );
};

/** Bar shown while the assistant's last change is highlighted on the canvas. */
export const PendingChangeBar: React.FC<{
  change: PendingChange;
  onKeep: () => void;
  onUndo: () => void;
}> = ({ change, onKeep, onUndo }) => (
  <div className="mx-3 mb-2 flex items-center gap-2 rounded-lg border border-[hsl(var(--brand-600))]/40 bg-[hsl(var(--brand-600))]/10 px-3 py-2 text-xs">
    <span className="min-w-0 flex-1 truncate text-foreground" title={change.summary}>
      The assistant changed {change.count} thing{change.count === 1 ? "" : "s"} (highlighted on the canvas).
    </span>
    <Button size="sm" variant="outline" className="h-7 text-xs" onClick={onUndo}>
      <Undo2 className="mr-1 h-3 w-3" />
      Undo
    </Button>
    <Button size="sm" className="h-7 text-xs" onClick={onKeep}>
      <Check className="mr-1 h-3 w-3" />
      Keep
    </Button>
  </div>
);
