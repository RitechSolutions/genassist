import React, { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/button";
import { Skeleton } from "@/components/skeleton";
import { cn } from "@/helpers/utils";
import type { RunConversationResult, RunTurnResult, TestRun, Verdict } from "@/interfaces/testSuite.interface";
import {
  COMPARE_GROUPS,
  compareGroup,
  compareRuns,
  comparisonOrder,
  excerpt,
  inTimeOrder,
  type CheckDetail,
  checkDetail,
  changedTurnsByCheck,
  pairChange,
  pairChecks,
  pairReplyChecks,
  pairTurnChecks,
  type ReplyCheckPair,
  pairTurns,
  runConversationLabels,
  turnCheckDetail,
} from "../helpers/runConversations";
import { runName } from "../helpers/runResults";
import { useRunConversations } from "../hooks/useRunConversations";
import {
  CheckDetailLine,
  CheckTrend,
  DatasetFact,
  Fact,
  HeaderCard,
  type RunContext,
  SideFact,
  VerdictIcon,
  WorkflowFact,
} from "./resultsParts";
import { MARK, MARKED, useTurnJump } from "../hooks/useTurnJump";
import { AgentReply, CustomerBubble, PILL } from "./conversationParts";
import { TurnCompareDialog } from "./TurnCompareDialog";
import { Transition } from "./RunCompareView";
import { TurnStepsDialog } from "./TurnStepsDialog";

interface Side {
  run: TestRun;
  conversation?: RunConversationResult;
}

interface CompareSide {
  status: Verdict;
  detail: CheckDetail;
}

// A row that got worse is tinted red, one that got better green; any other change amber.
const changeTint = (before?: CompareSide, after?: CompareSide): string | false => {
  if (!before || !after || before.status === after.status) return false;
  if (after.status === "failed") return "bg-destructive/5";
  if (after.status === "passed" && before.status === "failed") return "bg-emerald-500/5";
  return "bg-amber-500/5";
};

const sameDetail = (a: CheckDetail, b: CheckDetail): boolean =>
  a.text === b.text && a.lead === b.lead && a.turns.join() === b.turns.join() && (a.rest ?? null) === (b.rest ?? null);

/** Checks of one kind in two runs: each check's sentence and where it held or broke in each run, then a column per run. */
const CompareChecksTable: React.FC<{
  title: string;
  runs: [string, string];
  rows: {
    key: string;
    title: string;
    sides: [CompareSide | undefined, CompareSide | undefined];
    /** Said once for both runs, such as the one turn a turn check is on in each. */
    shared?: CheckDetail;
    /** The turns where this check went differently, by each run's numbers; only they are links. */
    changed?: { before: Set<number>; after: Set<number> };
  }[];
  /** Turn checks have filled icons, whole-conversation checks outlined. */
  filled?: boolean;
  onJump: (side: "before" | "after", turn: number) => void;
}> = ({ title, runs, rows, filled, onJump }) => {
  if (!rows.length) {
    return (
      <section className="rounded-lg border bg-card">
        <div className="border-b px-4 py-2.5 text-sm font-semibold">{title}</div>
        <p className="px-4 py-2.5 text-sm text-muted-foreground">No checks.</p>
      </section>
    );
  }
  return (
    <section className="rounded-lg border bg-card">
      <div className="grid grid-cols-[minmax(0,1fr)_4.5rem_4.5rem] items-center gap-3 border-b px-4 py-2.5 text-xs font-semibold text-muted-foreground">
        <span className="text-sm text-foreground">{title}</span>
        <span className="text-center">{runs[0]}</span>
        <span className="text-center">{runs[1]}</span>
      </div>
      <div className="divide-y">
        {rows.map((row) => (
          <div
            key={row.key}
            className={cn(
              "grid grid-cols-[minmax(0,1fr)_4.5rem_4.5rem] items-start gap-3 px-4 py-2.5",
              changeTint(row.sides[0], row.sides[1]),
            )}
          >
            <div className="min-w-0">
              <p className="text-sm">{row.title}</p>
              {/* Where it held or broke in each run, named by run, or once when it is the same in both. */}
              {row.shared ? (
                <CheckDetailLine
                  detail={row.shared}
                  onJump={(turn) => onJump("after", turn)}
                  linked={(turn) => Boolean(row.changed?.after.has(turn))}
                />
              ) : (
                row.sides.map((side, position) =>
                  side ? (
                    <CheckDetailLine
                      key={position}
                      detail={side.detail}
                      run={runs[position]}
                      onJump={(turn) => onJump(position === 0 ? "before" : "after", turn)}
                      linked={(turn) => Boolean(row.changed?.[position === 0 ? "before" : "after"].has(turn))}
                    />
                  ) : null,
                )
              )}
            </div>
            {row.sides.map((side, position) => (
              <span key={position} className="flex justify-center pt-0.5">
                {side ? (
                  <VerdictIcon verdict={side.status} filled={filled} />
                ) : (
                  <span className="text-xs text-muted-foreground" title="Not checked in this run">
                    <span aria-hidden="true">–</span>
                    <span className="sr-only">Not checked in this run</span>
                  </span>
                )}
              </span>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
};

/** A row's one checks pill: how many checks on the reply got worse or better, opening both runs side by side. */
const ChecksPill: React.FC<{ pairs: ReplyCheckPair[]; about: string; onOpen: () => void }> = ({
  pairs,
  about,
  onOpen,
}) => {
  if (!pairs.length) return null;
  const count = (change: "worse" | "better" | "changed") => pairs.filter((pair) => pairChange(pair) === change).length;
  const [worse, better, other] = [count("worse"), count("better"), count("changed")];
  const summary = [worse && `${worse} got worse`, better && `${better} got better`, other && `${other} changed`].filter(
    Boolean,
  );
  const said = summary.length ? summary.join(", ") : "No check changed";
  return (
    <button
      type="button"
      onClick={onOpen}
      title={said}
      aria-label={`Checks: ${said}. Compare the checks on the reply to “${excerpt(about, 40)}”`}
      className={cn(PILL, "gap-2.5")}
    >
      <span className="text-muted-foreground">Checks</span>
      <CheckTrend better={better} worse={worse} />
      {other > 0 && <span className="text-amber-700 dark:text-amber-400">{other} changed</span>}
      {!summary.length && <span className="font-normal text-muted-foreground">No change</span>}
      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
    </button>
  );
};

export interface CompareConversationViewProps {
  run: TestRun;
  other: TestRun;
  context?: RunContext;
  conversationKey: string;
  onBack: () => void;
  onNavigate: (key: string) => void;
}

/** One conversation in two runs, side by side: the same customer messages, each run's replies and checks. */
export const CompareConversationView: React.FC<CompareConversationViewProps> = ({
  run,
  other,
  context = {},
  conversationKey,
  onBack,
  onNavigate,
}) => {
  const { jump, ref, marked } = useTurnJump();
  const [before, after] = inTimeOrder(run, other);
  const earlier = useRunConversations(before);
  const later = useRunConversations(after);
  const [steps, setSteps] = useState<{ run: TestRun; turn: RunTurnResult } | null>(null);
  // The turn whose checks are compared in the dialog.
  const [compared, setCompared] = useState<string | null>(null);
  const comparison = useMemo(
    () => (earlier.data && later.data ? compareRuns(earlier.data, later.data) : null),
    [earlier.data, later.data],
  );
  const order = useMemo(() => (comparison ? comparisonOrder(comparison) : []), [comparison]);
  const labels = useMemo(
    () =>
      new Map([
        ...runConversationLabels(earlier.data?.conversations ?? []),
        ...runConversationLabels(later.data?.conversations ?? []),
      ]),
    [earlier.data, later.data],
  );

  if (earlier.isLoading || later.isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-80" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const index = order.findIndex((change) => change.key === conversationKey);
  const change = order[index];
  if (!comparison || !change) {
    return (
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={onBack} aria-label="Back to the comparison">
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <p className={cn("text-sm", comparison ? "text-muted-foreground" : "text-destructive")}>
          {comparison ? "This conversation is in neither run." : "The results could not be loaded."}
        </p>
      </div>
    );
  }

  const previous = index > 0 ? order[index - 1] : null;
  const next = index < order.length - 1 ? order[index + 1] : null;
  const sides: [Side, Side] = [
    { run: before, conversation: earlier.data?.conversations.find((item) => item.key === conversationKey) },
    { run: after, conversation: later.data?.conversations.find((item) => item.key === conversationKey) },
  ];
  const label = labels.get(conversationKey) ?? conversationKey;
  const group = compareGroup(change);
  const groupTitle = COMPARE_GROUPS.find((entry) => entry.group === group)?.title ?? "Not compared";
  const wholeConversation = pairChecks(sides[0].conversation, sides[1].conversation);
  const turns = pairTurns(sides[0].conversation, sides[1].conversation);
  const turnPairs = pairTurnChecks(sides[0].conversation, sides[1].conversation);
  // Only a turn where a check went differently is worth jumping to.
  const changedTurns = changedTurnsByCheck(sides[0].conversation, sides[1].conversation);
  // A turn number is the run's own, so it finds its row through that run's side.
  const jumpTo = (side: "before" | "after", number: number) => {
    const pair = turns.find((entry) => entry[side]?.number === number);
    if (pair) jump(pair.key);
  };
  const turnCount = turns.length;

  // What changed on a row is said once, by its checks pill.
  const reply = (side: Side, turn: RunTurnResult | undefined) =>
    side.conversation && turn ? (
      <AgentReply
        fill
        turn={turn}
        conversation={side.conversation}
        speaker={runName(side.run)}
        onShowSteps={() => setSteps({ run: side.run, turn })}
      />
    ) : (
      <div className="flex flex-col">
        <span className="mb-1 text-[11px] font-medium text-muted-foreground">{runName(side.run)}</span>
        <div className="rounded-lg border border-dashed px-3 py-2 text-sm italic text-muted-foreground">
          Not in this run
        </div>
      </div>
    );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start gap-2">
        <Button variant="ghost" size="icon" onClick={onBack} className="shrink-0" aria-label="Back to the comparison">
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <div className="flex min-w-0 flex-1 items-center gap-2 self-center">
          <Transition before={change.before} after={change.after} className="text-xl" />
          <h1 className="truncate text-2xl font-bold tracking-tight">{label}</h1>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!previous}
            onClick={() => previous && onNavigate(previous.key)}
            aria-label="Previous conversation"
          >
            <ChevronLeft className="mr-1 h-4 w-4" />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!next}
            onClick={() => next && onNavigate(next.key)}
            aria-label="Next conversation"
          >
            Next
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="space-y-6">
        <HeaderCard
          outcome={
            <div>
              <Transition before={change.before} after={change.after} className="text-3xl" />
              <div className="mt-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">{groupTitle}</div>
            </div>
          }
        >
          <WorkflowFact run={after} context={context} version={false} />
          <DatasetFact run={after} context={context} />
          <Fact label="Turns">
            {turnCount} turn{turnCount === 1 ? "" : "s"}
          </Fact>
          <SideFact label="Before" run={before} />
          <SideFact label="After" run={after} />
        </HeaderCard>

        {/* Side by side: the whole conversation's checks on the left, the turns' on the right. */}
        <div className="grid items-start gap-6 lg:grid-cols-2">
          <CompareChecksTable
            title="Whole conversation"
            runs={[runName(before), runName(after)]}
            rows={wholeConversation.map((row) => {
              const pair = ([row.before, row.after] as const).map((item, position) =>
                item
                  ? { status: item.status, detail: checkDetail(item, sides[position].conversation?.turns.length) }
                  : undefined,
              ) as [CompareSide | undefined, CompareSide | undefined];
              // Said once when both runs say the same, so only a difference takes two lines.
              const shared =
                pair[0] && pair[1] && sameDetail(pair[0].detail, pair[1].detail) ? pair[1].detail : undefined;
              return {
                key: row.key,
                title: row.title,
                sides: pair,
                shared,
                changed: changedTurns.get(`whole:${row.title}`),
              };
            })}
            onJump={jumpTo}
          />
          <CompareChecksTable
            title="Turn checks"
            filled
            runs={[runName(before), runName(after)]}
            rows={turnPairs.map((row) => ({
              key: row.key,
              title: row.title,
              changed: changedTurns.get(`turn:${row.title}`),
              sides: [row.before, row.after].map((side) =>
                side ? { status: side.item.status, detail: turnCheckDetail(side.item, side.turn) } : undefined,
              ) as [CompareSide | undefined, CompareSide | undefined],
              // The same turn in both runs is named once, unless a run has a reason of its own to say.
              shared:
                row.before &&
                row.after &&
                row.before.turn === row.after.turn &&
                ![row.before, row.after].some((side) => side.item.status === "not_evaluated")
                  ? { text: null, lead: null, turns: [row.after.turn], facts: [] }
                  : undefined,
            }))}
            onJump={jumpTo}
          />
        </div>

        <div className="space-y-6 rounded-lg border bg-card p-4 sm:p-6">
          {turns.map(({ key, before: earlierTurn, after: laterTurn }) => (
            <div key={key} ref={ref(key)} className={cn("space-y-3", MARK, marked === key && MARKED)}>
              <CustomerBubble message={(laterTurn ?? earlierTurn)?.message ?? ""} />
              <div className="grid gap-4 md:grid-cols-2">
                {reply(sides[0], earlierTurn)}
                {reply(sides[1], laterTurn)}
              </div>
              {/* Centred, as it compares both replies rather than belonging to one. */}
              <div className="flex justify-center">
                <ChecksPill
                  pairs={pairReplyChecks(
                    earlierTurn && sides[0].conversation
                      ? { turn: earlierTurn, conversation: sides[0].conversation }
                      : undefined,
                    laterTurn && sides[1].conversation
                      ? { turn: laterTurn, conversation: sides[1].conversation }
                      : undefined,
                  )}
                  about={(laterTurn ?? earlierTurn)?.message ?? ""}
                  onOpen={() => setCompared(key)}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {steps?.run.id && (
        <TurnStepsDialog
          open
          onOpenChange={(open) => !open && setSteps(null)}
          runId={steps.run.id}
          caseId={steps.turn.case_id}
          workflowId={steps.run.workflow_id}
          runCreatedAt={steps.run.created_at}
          title={`Steps · ${runName(steps.run)}`}
          description={`How the workflow answered “${excerpt(steps.turn.message)}”. Select a step to see what went in and what came out.`}
        />
      )}
      {compared &&
        (() => {
          const pair = turns.find((entry) => entry.key === compared);
          return pair ? (
            <TurnCompareDialog
              before={{ run: runName(before), turn: pair.before, conversation: sides[0].conversation }}
              after={{ run: runName(after), turn: pair.after, conversation: sides[1].conversation }}
              onClose={() => setCompared(null)}
            />
          ) : null;
        })()}
    </div>
  );
};
