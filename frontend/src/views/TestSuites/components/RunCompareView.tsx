import React, { useMemo, useState } from "react";
import {
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  CircleArrowDown,
  CircleArrowUp,
  CircleDashed,
  CircleEqual,
  GitCompareArrows,
  Minus,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/button";
import { Skeleton } from "@/components/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/select";
import { cn } from "@/helpers/utils";
import type { TestRun, Verdict } from "@/interfaces/testSuite.interface";
import {
  COMPARE_GROUPS,
  type CompareGroup,
  type ComparisonVerdict,
  type ConversationChange,
  compareGroup,
  checkMovesText,
  hiddenCheckMoves,
  compareRuns,
  conversationFindings,
  inTimeOrder,
  notComparedReason,
  runChecks,
  runConversationLabels,
  verdictLabel,
} from "../helpers/runConversations";
import { useRunConversations } from "../hooks/useRunConversations";
import {
  CheckTrend,
  DatasetFact,
  Fact,
  HeaderCard,
  type RunContext,
  SideFact,
  VerdictIcon,
  WorkflowFact,
} from "./resultsParts";
import { runName, runOptionLabel } from "../helpers/runResults";
import type { CheckConversation } from "../helpers/checks";
import { ChecksDialog } from "./ChecksDialog";

const VERDICT: Record<ComparisonVerdict, { label: string; icon: React.ElementType; className: string }> = {
  better: { label: "Better", icon: CircleArrowUp, className: "text-emerald-600 dark:text-emerald-400" },
  worse: { label: "Worse", icon: CircleArrowDown, className: "text-destructive" },
  // New failures weigh more than fixes, so Mixed reads as a warning.
  mixed: { label: "Mixed", icon: CircleAlert, className: "text-amber-600 dark:text-amber-400" },
  same: { label: "Same", icon: CircleEqual, className: "text-muted-foreground" },
};

/** The header's left side: how the later run did against the earlier one. */
const Outcome: React.FC<{ icon: React.ElementType; label: string; className: string }> = ({
  icon: Icon,
  label,
  className,
}) => (
  <div className="flex flex-col items-center">
    <Icon className={cn("h-9 w-9", className)} aria-hidden="true" />
    <div className="mt-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
  </div>
);

// A count with conversations gets a red or green border; an empty one fades.
const CARD_TONE: Record<Exclude<CompareGroup, "not_compared">, string> = {
  newly_failing: "border-destructive/60",
  still_failing: "border-destructive/60",
  newly_passing: "border-emerald-500/60",
  still_passing: "border-emerald-500/60",
};

const sectionId = (group: CompareGroup) => `compare-${group}`;

// A dashed circle where a run has no such conversation, so the arrow never points from nothing.
const NotInRun: React.FC = () => (
  <CircleDashed aria-hidden="true" className="h-[1em] w-[1em] text-muted-foreground/60" />
);

/** "✓ → ✗", read out as words. */
export const Transition: React.FC<{ before: Verdict | null; after: Verdict | null; className?: string }> = ({
  before,
  after,
  className,
}) => (
  <span
    role="img"
    aria-label={`${before ? verdictLabel(before) : "Not in the run"}, then ${
      after ? verdictLabel(after).toLowerCase() : "not in the run"
    }`}
    className={cn("flex shrink-0 items-center gap-1", className)}
  >
    {before ? <VerdictIcon verdict={before} className="h-[1em] w-[1em]" /> : <NotInRun />}
    <ArrowRight aria-hidden="true" className="h-[0.75em] w-[0.75em] text-muted-foreground" />
    {after ? <VerdictIcon verdict={after} className="h-[1em] w-[1em]" /> : <NotInRun />}
  </span>
);

const ChangeRow: React.FC<{
  change: ConversationChange;
  label: string;
  reason?: string | null;
  onOpen: () => void;
}> = ({ change, label, reason, onOpen }) => {
  const finding = change.after === "failed" ? conversationFindings(change.conversation)[0] : null;
  const detail = reason ?? finding;
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex w-full items-center gap-3 rounded-lg border bg-card p-3 text-left transition-colors hover:bg-muted"
    >
      <Transition before={change.before} after={change.after} className="text-base" />
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{label}</p>
        {detail && <p className="truncate text-sm text-muted-foreground">{detail}</p>}
      </div>
      {/* Checks that moved while its result stayed the same; a changed result already says so. */}
      {hiddenCheckMoves(change) && (
        <span
          className="flex shrink-0 items-center gap-2.5 rounded-full border px-2.5 py-0.5 text-xs font-medium"
          title={checkMovesText(change.checks)}
        >
          <CheckTrend {...change.checks} />
          <span className="sr-only">{checkMovesText(change.checks)}</span>
        </span>
      )}
      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
    </button>
  );
};

/** One run's picker, showing each completed run with its version and time. */
const RunPicker: React.FC<{
  value: string;
  runs: TestRun[];
  label: string;
  placeholder?: string;
  onChange: (runId: string) => void;
}> = ({ value, runs, label, placeholder, onChange }) => {
  const picked = runs.find((run) => run.id === value);
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-full sm:w-40" aria-label={label}>
        {/* The list gives each run's version and time; once picked, its name is enough. */}
        <SelectValue placeholder={placeholder}>{picked ? runName(picked) : undefined}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {runs.map((run) => (
          <SelectItem key={run.id} value={run.id ?? ""}>
            {runOptionLabel(run)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};

const plural = (count: number, noun: string) => `${count} ${noun}${count === 1 ? "" : "s"}`;

export interface RunCompareViewProps {
  /** The run picked first: the last run, unless changed. */
  run: TestRun;
  /** The run to compare it with, null until one is picked. */
  other: TestRun | null;
  /** The evaluation's runs, to pick from. */
  runs: TestRun[];
  context: RunContext;
  /** The dataset's conversations, to name the ones a check is for. */
  conversations: CheckConversation[];
  conversationsReady: boolean;
  backLabel: string;
  onBack: () => void;
  /** Called with both picks; the second is "" when it is cleared. */
  onChangeRuns: (runId: string, otherId: string) => void;
  onOpenConversation: (key: string) => void;
}

/** Two runs of one evaluation, compared conversation by conversation: four counts, then the conversations behind each. */
export const RunCompareView: React.FC<RunCompareViewProps> = ({
  run,
  other,
  runs,
  context,
  conversations,
  conversationsReady,
  backLabel,
  onBack,
  onChangeRuns,
  onOpenConversation,
}) => {
  // Changes read forward in time, whichever run was picked first.
  const [before, after] = other ? inTimeOrder(run, other) : [null, run];
  const earlier = useRunConversations(before);
  // The later run loads on its own too, so the header fills in before a second run is picked.
  const later = useRunConversations(after);
  const [showChecks, setShowChecks] = useState(false);
  const checks = useMemo(() => (later.data ? runChecks(later.data) : null), [later.data]);
  const comparison = useMemo(
    () => (earlier.data && later.data ? compareRuns(earlier.data, later.data) : null),
    [earlier.data, later.data],
  );
  const conversationCount = comparison?.changes.length ?? later.data?.counts.total;
  const labels = useMemo(
    () =>
      new Map([
        ...runConversationLabels(earlier.data?.conversations ?? []),
        ...runConversationLabels(later.data?.conversations ?? []),
      ]),
    [earlier.data, later.data],
  );
  const completed = runs.filter((item) => item.id && item.status === "completed");
  // A run picked from a link stays listed even when it did not complete.
  const choices = (picked: TestRun | null, without: TestRun | null) =>
    [...(picked && !completed.some((item) => item.id === picked.id) ? [picked] : []), ...completed].filter(
      (item) => item.id !== without?.id,
    );
  // Within a group, conversations whose checks moved without changing their result come first.
  const moved = (change: ConversationChange) => (hiddenCheckMoves(change) ? 0 : 1);
  const grouped = (group: CompareGroup) =>
    (comparison?.changes.filter((change) => compareGroup(change) === group) ?? []).sort((a, b) => moved(a) - moved(b));
  const notCompared = grouped("not_compared");
  const beforeName = before ? runName(before) : "";
  const afterName = runName(after);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start gap-2">
        <Button variant="ghost" size="icon" onClick={onBack} className="shrink-0" aria-label={backLabel}>
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl font-bold tracking-tight">Compare runs</h1>
          <p className="text-sm text-muted-foreground">
            How each conversation went from the earlier run to the later one.
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-center sm:gap-3">
        <RunPicker
          value={run.id ?? ""}
          runs={choices(run, other)}
          label="Run"
          onChange={(runId) => onChangeRuns(runId, other?.id ?? "")}
        />
        <span className="text-sm text-muted-foreground">compared with</span>
        <RunPicker
          value={other?.id ?? ""}
          runs={choices(other, run)}
          label="Run to compare with"
          placeholder="Select run"
          onChange={(otherId) => onChangeRuns(run.id ?? "", otherId)}
        />
      </div>

      <HeaderCard
        outcome={
          comparison ? (
            <Outcome {...VERDICT[comparison.verdict]} />
          ) : other ? (
            <Skeleton className="h-16 w-16" />
          ) : (
            <Outcome icon={GitCompareArrows} label="Pick a run" className="text-muted-foreground/60" />
          )
        }
      >
        <WorkflowFact run={after} context={context} version={false} />
        <DatasetFact
          run={after}
          context={context}
          note={conversationCount !== undefined ? plural(conversationCount, "conversation") : undefined}
        />
        <Fact label="Checks">
          {checks === null ? (
            "…"
          ) : (
            <>
              {plural(checks.length, "check")}
              {checks.length > 0 && (
                <button
                  type="button"
                  onClick={() => setShowChecks(true)}
                  aria-haspopup="dialog"
                  className="ml-2 text-xs font-medium text-primary hover:underline"
                >
                  Show
                </button>
              )}
            </>
          )}
        </Fact>
        <SideFact label="Before" run={before} />
        <SideFact label="After" run={other ? after : null} />
        {/* The pills on the rows together: checks that flipped where a conversation's result did not. */}
        {comparison && (comparison.checks.better > 0 || comparison.checks.worse > 0) && (
          <Fact label="Checks that changed">
            <span className="flex flex-col gap-0.5">
              {comparison.checks.better > 0 && (
                <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
                  <TrendingUp className="h-4 w-4 shrink-0" aria-hidden="true" />
                  {comparison.checks.better} used to fail, now pass{comparison.checks.better === 1 ? "es" : ""}
                </span>
              )}
              {comparison.checks.worse > 0 && (
                <span className="flex items-center gap-1.5 text-destructive">
                  <TrendingDown className="h-4 w-4 shrink-0" aria-hidden="true" />
                  {comparison.checks.worse} used to pass, now fail{comparison.checks.worse === 1 ? "s" : ""}
                </span>
              )}
            </span>
          </Fact>
        )}
        {/* Not compared below, but a lost pass makes the verdict worse, so the header says why. */}
        {comparison && (comparison.noLongerEvaluated.passed > 0 || comparison.noLongerEvaluated.failed > 0) && (
          <Fact label="No longer evaluated">
            <span className="flex flex-col gap-0.5">
              {comparison.noLongerEvaluated.passed > 0 && (
                <span className="flex items-center gap-1.5 text-destructive">
                  <TrendingDown className="h-4 w-4 shrink-0" aria-hidden="true" />
                  {comparison.noLongerEvaluated.passed} used to pass
                </span>
              )}
              {comparison.noLongerEvaluated.failed > 0 && (
                <span className="flex items-center gap-1.5">
                  <Minus className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  {comparison.noLongerEvaluated.failed} used to fail
                </span>
              )}
            </span>
          </Fact>
        )}
      </HeaderCard>
      <ChecksDialog
        open={showChecks}
        onOpenChange={setShowChecks}
        checks={checks ?? []}
        description={`The checks as ${afterName} graded them.`}
        conversations={conversations}
        conversationsReady={conversationsReady}
      />

      {!other ? (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed py-12 text-center">
          <GitCompareArrows className="h-8 w-8 text-muted-foreground/60" />
          <p className="max-w-sm text-sm text-muted-foreground">
            Pick a run to compare {runName(run)} with. The page then shows which conversations newly fail, still fail,
            newly pass or still pass.
          </p>
        </div>
      ) : earlier.isLoading || later.isLoading ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[1, 2, 3, 4].map((key) => (
              <Skeleton key={key} className="h-28 w-full" />
            ))}
          </div>
          <Skeleton className="h-16 w-full" />
        </div>
      ) : !comparison ? (
        <p className="text-sm text-destructive">The results could not be loaded.</p>
      ) : (
        <>
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {COMPARE_GROUPS.map(({ group, title, before: from, after: to }) => {
                const count = grouped(group).length;
                return (
                  <button
                    key={group}
                    type="button"
                    disabled={!count}
                    onClick={() =>
                      document.getElementById(sectionId(group))?.scrollIntoView({ block: "start", behavior: "smooth" })
                    }
                    className={cn(
                      "flex flex-col items-center gap-1 rounded-lg border bg-card p-4 text-center transition-colors enabled:hover:bg-muted",
                      count ? CARD_TONE[group] : "opacity-60",
                    )}
                  >
                    <Transition before={from} after={to} className="text-xl" />
                    <span className="text-3xl font-semibold tabular-nums">{count}</span>
                    <span className="text-sm text-muted-foreground">{title}</span>
                  </button>
                );
              })}
            </div>
            {notCompared.length > 0 && (
              <p className="text-sm text-muted-foreground">
                {notCompared.length} conversation{notCompared.length === 1 ? " was" : "s were"} not compared, as{" "}
                {notCompared.length === 1 ? "it was" : "they were"} not evaluated in a run or{" "}
                {notCompared.length === 1 ? "is" : "are"} in one run only.
              </p>
            )}
          </div>

          {[...COMPARE_GROUPS, { group: "not_compared" as const, title: "Not compared" }].map(({ group, title }) => {
            const changes = grouped(group);
            if (!changes.length) return null;
            return (
              <section key={group} id={sectionId(group)} className="scroll-mt-6 space-y-2">
                <h2 className="text-sm font-semibold">
                  {title} <span className="font-normal text-muted-foreground">{changes.length}</span>
                </h2>
                <div className="space-y-2">
                  {changes.map((change) => (
                    <ChangeRow
                      key={change.key}
                      change={change}
                      label={labels.get(change.key) ?? change.key}
                      reason={group === "not_compared" ? notComparedReason(change, beforeName, afterName) : null}
                      onOpen={() => onOpenConversation(change.key)}
                    />
                  ))}
                </div>
              </section>
            );
          })}
        </>
      )}
    </div>
  );
};
