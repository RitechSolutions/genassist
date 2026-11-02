import React from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Loader2, MinusCircle, TrendingDown, TrendingUp, XCircle } from "lucide-react";
import { cn } from "@/helpers/utils";
import type { ConversationCounts, TestRun, Verdict } from "@/interfaces/testSuite.interface";
import {
  type CheckDetail,
  checkDetail,
  conversationsVerdictText,
  type GradedItem,
  turnCheckDetail,
} from "../helpers/runConversations";
import { runDate, runName } from "../helpers/runResults";

const VERDICT_META: Record<Verdict, { icon: typeof CheckCircle2; className: string; label: string }> = {
  passed: { icon: CheckCircle2, className: "text-emerald-600 dark:text-emerald-400", label: "Passed" },
  failed: { icon: XCircle, className: "text-destructive", label: "Failed" },
  not_evaluated: { icon: MinusCircle, className: "text-muted-foreground", label: "Not evaluated" },
};

// A filled icon marks what is about one reply, such as a turn's own check; an outlined one, the whole conversation.
const FILLED: Record<Verdict, string> = {
  passed: "fill-emerald-600 text-white dark:fill-emerald-500 dark:text-zinc-900",
  failed: "fill-destructive text-white dark:text-zinc-900",
  not_evaluated: "fill-muted-foreground text-white dark:text-zinc-900",
};

export const VerdictIcon: React.FC<{ verdict: Verdict; className?: string; filled?: boolean }> = ({
  verdict,
  className,
  filled,
}) => {
  const meta = VERDICT_META[verdict] ?? VERDICT_META.not_evaluated;
  const Icon = meta.icon;
  return (
    <Icon
      role="img"
      aria-label={meta.label}
      className={cn("h-4 w-4 shrink-0", meta.className, filled && FILLED[verdict], className)}
    />
  );
};

// A zero stays readable but faint, so the eye skips it.
const ZERO = "font-normal text-muted-foreground/50";

/** A run still going, in blue with a spinner, where its results will appear. */
export const RunningStatus: React.FC<{ children: React.ReactNode; className?: string; iconClassName?: string }> = ({
  children,
  className,
  iconClassName = "h-3 w-3",
}) => (
  <span className={cn("inline-flex items-center gap-1.5 font-medium text-blue-600 dark:text-blue-400", className)}>
    <Loader2 className={cn("shrink-0 animate-spin", iconClassName)} aria-hidden="true" />
    {children}
  </span>
);

/** A run's conversations as passed and failed out of all, plus not evaluated when there are some. */
export const VerdictTally: React.FC<{
  counts: ConversationCounts;
  className?: string;
  iconClassName?: string;
  /** A fixed slot for each of these verdicts, so tallies stacked in a column line up. */
  slots?: Verdict[];
}> = ({ counts, className, iconClassName, slots }) => {
  const all: [Verdict, number][] = [
    ["passed", counts.passed],
    ["failed", counts.failed],
    ["not_evaluated", counts.not_evaluated ?? 0],
  ];
  // Passed and failed always, zero included; not evaluated only when some were.
  const shown = all.filter(([verdict, count]) => verdict !== "not_evaluated" || count > 0);
  const sentence = conversationsVerdictText(counts);
  if (slots) {
    return (
      <span
        role="img"
        aria-label={sentence}
        title={sentence}
        className={cn("inline-flex items-center tabular-nums", className)}
      >
        {all
          .filter(([verdict]) => slots.includes(verdict))
          .map(([verdict, count]) => (
            // Sized in em so the slot grows with the text; room for "99/99".
            <span
              key={verdict}
              aria-hidden="true"
              className={cn("inline-flex w-[4.75em] items-center gap-1", !count && ZERO)}
            >
              {shown.some(([kept]) => kept === verdict) && (
                <>
                  <VerdictIcon verdict={verdict} className={cn(!count && ZERO, iconClassName)} />
                  {count}/{counts.total}
                </>
              )}
            </span>
          ))}
      </span>
    );
  }
  return (
    <span
      role="img"
      aria-label={sentence}
      title={sentence}
      className={cn("inline-flex items-center gap-3 tabular-nums", className)}
    >
      {shown.map(([verdict, count]) => (
        <span key={verdict} aria-hidden="true" className={cn("inline-flex items-center gap-1", !count && ZERO)}>
          <VerdictIcon verdict={verdict} className={cn(!count && ZERO, iconClassName)} />
          {count}/{counts.total}
        </span>
      ))}
    </span>
  );
};

/** One verdict's count, large, over its name; a zero is faint like in the tallies. */
export const VerdictStat: React.FC<{ verdict: Verdict; count: number; total: number; label?: string }> = ({
  verdict,
  count,
  total,
  label,
}) => (
  <div className="min-w-0">
    <div className={cn("flex items-center gap-2 text-3xl font-semibold leading-none tabular-nums", !count && ZERO)}>
      <VerdictIcon verdict={verdict} className={cn("h-7 w-7", !count && ZERO)} />
      <span>
        {count}
        <span className={cn("text-lg font-normal", count > 0 && "text-muted-foreground")}>/{total}</span>
      </span>
    </div>
    <div className="mt-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
      {label ?? VERDICT_META[verdict].label}
    </div>
  </div>
);

/** Passed and failed, large, and not evaluated when there are some; the noun says what was counted. */
export const VerdictStats: React.FC<{ counts: ConversationCounts; noun?: string }> = ({ counts, noun }) => (
  <>
    <VerdictStat verdict="passed" count={counts.passed} total={counts.total} label={noun && `${noun} passed`} />
    <VerdictStat verdict="failed" count={counts.failed} total={counts.total} label={noun && `${noun} failed`} />
    {counts.not_evaluated > 0 && (
      <VerdictStat
        verdict="not_evaluated"
        count={counts.not_evaluated}
        total={counts.total}
        label={noun && `${noun} not evaluated`}
      />
    )}
  </>
);

/** A results page's header: the outcome, large, on the left; what ran and when on the right. */
export const HeaderCard: React.FC<{ outcome?: React.ReactNode; children: React.ReactNode }> = ({
  outcome,
  children,
}) => (
  <div className="flex flex-col rounded-lg border bg-card dark:bg-zinc-900 lg:flex-row">
    {outcome && <div className="flex items-center gap-8 border-b p-5 lg:border-b-0 lg:border-r lg:px-8">{outcome}</div>}
    <div className="grid flex-1 grid-cols-2 gap-x-6 gap-y-5 p-5 sm:grid-cols-3">{children}</div>
  </div>
);

export const Fact: React.FC<{ label: string; children: React.ReactNode; note?: React.ReactNode }> = ({
  label,
  children,
  note,
}) => (
  <div className="min-w-0">
    <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
    <div className="mt-1 truncate text-sm font-medium">{children}</div>
    {note && <div className="truncate text-xs text-muted-foreground">{note}</div>}
  </div>
);

/** Where the results page sits: the workflow and dataset names a run does not carry, and whether it is in the builder. */
export interface RunContext {
  /** The workflow's own name; a run only knows its version's. */
  workflowName?: string;
  workflowAgentId?: string;
  datasetName?: string;
  /** Inside the workflow builder. */
  embedded?: boolean;
}

const LINK = "block truncate text-primary hover:underline";

/** The workflow, opened at the version the run played; with two runs, without one version of its own. */
export const WorkflowFact: React.FC<{ run: TestRun; context: RunContext; version?: boolean }> = ({
  run,
  context,
  version = true,
}) => {
  const name = context.workflowName ?? run.workflow_name ?? "Its workflow";
  const query = version ? `?version=${run.workflow_id}` : "";
  return (
    <Fact label="Workflow" note={version && run.workflow_version ? `Version ${run.workflow_version}` : undefined}>
      {/* Inside the builder the workflow is the one already open. */}
      {context.workflowAgentId && !context.embedded ? (
        <Link to={`/ai-agents/workflow/${context.workflowAgentId}${query}`} className={LINK}>
          {name}
        </Link>
      ) : (
        name
      )}
    </Fact>
  );
};

export const DatasetFact: React.FC<{ run: TestRun; context: RunContext; note?: React.ReactNode }> = ({
  run,
  context,
  note,
}) => (
  <Fact label="Dataset" note={note}>
    {/* From the builder it opens apart, so the builder stays as it was. */}
    <Link
      to={`/tests/datasets/${run.suite_id}`}
      target={context.embedded ? "_blank" : undefined}
      rel={context.embedded ? "noreferrer" : undefined}
      className={LINK}
    >
      {context.datasetName ?? "Its dataset"}
    </Link>
  </Fact>
);

/** One side of the comparison: the run, its workflow version and when it ran. */
export const SideFact: React.FC<{ label: string; run: TestRun | null }> = ({ label, run }) => (
  <Fact
    label={label}
    note={
      run && (
        <>
          {run.workflow_version && <div className="truncate">Workflow version: {run.workflow_version}</div>}
          <div className="truncate">Ran on: {runDate(run)}</div>
        </>
      )
    }
  >
    {run ? runName(run) : <span className="font-normal text-muted-foreground">Not picked</span>}
  </Fact>
);

/** How many checks got better and worse: a green rising arrow and a red falling one, each with its count. */
export const CheckTrend: React.FC<{ better: number; worse: number }> = ({ better, worse }) => (
  <>
    {worse > 0 && (
      <span className="flex items-center gap-1 text-destructive">
        <TrendingDown className="h-3.5 w-3.5" aria-hidden="true" />
        {worse}
      </span>
    )}
    {better > 0 && (
      <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
        <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
        {better}
      </span>
    )}
  </>
);

/** Where a whole-conversation check held or broke: its own sentence, or the turns, each a link that brings it into view. */
export const CheckDetailLine: React.FC<{
  detail: CheckDetail;
  /** Names the run it belongs to, on a page with two. */
  run?: string;
  onJump?: (turn: number) => void;
  /** Only these turns are links; the rest are named as plain text. */
  linked?: (turn: number) => boolean;
}> = ({ detail, run, onJump, linked = () => true }) => {
  if (!detail.text && !detail.turns.length) return null;
  const tag = run && (
    <span className="mr-1.5 rounded bg-foreground/5 px-1.5 py-px text-[11px] font-medium text-foreground/60">
      {run}
    </span>
  );
  return (
    <>
      {detail.text && (
        <p className="mt-0.5 text-xs text-muted-foreground">
          {tag}
          {detail.text}
        </p>
      )}
      {detail.turns.length > 0 && (
        <p className="mt-0.5 text-xs text-muted-foreground">
          {!detail.text && tag}
          {detail.lead && `${detail.lead}: `}
          {detail.turns.map((turn, index) => (
            <React.Fragment key={turn}>
              {index > 0 && ", "}
              {onJump && linked(turn) ? (
                // What the turn did shows on hover.
                <button
                  type="button"
                  title={detail.facts[index]}
                  onClick={() => onJump(turn)}
                  className="font-medium text-primary hover:underline"
                >
                  Turn {turn}
                </button>
              ) : (
                <span title={detail.facts[index]}>Turn {turn}</span>
              )}
            </React.Fragment>
          ))}
          {detail.rest && `. ${detail.rest}`}
        </p>
      )}
    </>
  );
};

/** A turn check: its sentence, filled, then the turn it held or broke on, as a link. */
export const TurnCheckRow: React.FC<{ item: GradedItem; turn: number; onJump?: (turn: number) => void }> = ({
  item,
  turn,
  onJump,
}) => (
  <div className="flex items-start gap-2">
    <VerdictIcon verdict={item.status} className="mt-0.5" filled />
    <div className="min-w-0 flex-1">
      <p className="text-sm">{item.title}</p>
      <CheckDetailLine detail={turnCheckDetail(item, turn)} onJump={onJump} />
    </div>
  </div>
);

/** A whole-conversation check: its sentence, then where it held or broke. */
export const ConversationCheckRow: React.FC<{
  item: GradedItem;
  turnCount: number;
  onJump?: (turn: number) => void;
}> = ({ item, turnCount, onJump }) => (
  <div className="flex items-start gap-2">
    <VerdictIcon verdict={item.status} className="mt-0.5" />
    <div className="min-w-0 flex-1">
      <p className="text-sm">{item.title}</p>
      <CheckDetailLine detail={checkDetail(item, turnCount)} onJump={onJump} />
    </div>
  </div>
);

const Label: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{children}</div>
);

/** A labelled block of text that keeps the reply's own line breaks. */
export const TextBlock: React.FC<{
  label: string;
  text?: string | null;
  empty?: string;
  tone?: "default" | "failed";
}> = ({ label, text, empty = "Nothing", tone = "default" }) => (
  <div className="min-w-0 space-y-1">
    <Label>{label}</Label>
    <p
      className={cn(
        "whitespace-pre-wrap break-words text-sm",
        !text && "italic text-muted-foreground",
        text && tone === "failed" && "text-destructive",
      )}
    >
      {text || empty}
    </p>
  </div>
);

/** One check or method: what it expected and, when it did not pass, what happened instead. */
export const GradedItemRow: React.FC<{
  item: GradedItem;
  showMethod?: boolean;
  /** Filled for what is about one reply; a turn's own check is, from its scope. */
  filled?: boolean;
}> = ({ item, showMethod, filled = item.whole === false }) => {
  const open = item.status !== "passed";
  const actualTone = item.status === "failed" ? "failed" : "default";
  // A check's sentence is what it expected, so it sits next to what happened.
  const titleIsExpected = open && !item.expected && Boolean(item.actual);
  const pair = open && !titleIsExpected && (item.expected || item.actual);
  return (
    <div className="space-y-1.5">
      <div className="flex items-start gap-2">
        <VerdictIcon verdict={item.status} className="mt-0.5" filled={filled} />
        {titleIsExpected ? (
          <div className="grid min-w-0 flex-1 gap-2 sm:grid-cols-2">
            <TextBlock label="Expected" text={item.title} />
            <TextBlock label="Actual" text={item.actual} tone={actualTone} />
          </div>
        ) : (
          <div className="min-w-0 flex-1">
            <p className="text-sm">
              {item.title}
              {showMethod && item.method && item.method !== item.title && (
                <span className="ml-1.5 text-xs text-muted-foreground">{item.method}</span>
              )}
            </p>
            {item.status === "passed" && item.actual && <p className="text-xs text-muted-foreground">{item.actual}</p>}
          </div>
        )}
      </div>
      {pair && (
        <div className={cn("ml-6 grid gap-2", item.expected && item.actual && "sm:grid-cols-2")}>
          {item.expected && <TextBlock label="Expected" text={item.expected} />}
          {item.actual && <TextBlock label="Actual" text={item.actual} tone={actualTone} />}
        </div>
      )}
      {open && item.note && <p className="ml-6 text-xs text-muted-foreground">{item.note}</p>}
      {item.items && item.items.length > 0 && (
        <div className="ml-6 space-y-1.5 border-l pl-3">
          {item.items.map((sub) => (
            <GradedItemRow key={sub.key} item={sub} />
          ))}
        </div>
      )}
    </div>
  );
};

/** Says when verdicts can still change, or were given without the run's checks. */
export const PendingRulesNote: React.FC<{ run: TestRun; pending?: boolean }> = ({ run, pending }) => {
  if (!pending) return null;
  const text =
    run.status === "failed"
      ? "The run failed before its checks were graded, so these results leave them out."
      : "Some checks are graded when the run ends, so these results can still change.";
  return (
    <p className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-800 dark:text-amber-300">
      {text}
    </p>
  );
};
