import React, { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/button";
import { cn } from "@/helpers/utils";
import { Skeleton } from "@/components/skeleton";
import type { RunTurnResult, TestRun } from "@/interfaces/testSuite.interface";
import {
  type GradedItem,
  conversationCheckCounts,
  excerpt,
  turnCheckRows,
  reviewOrder,
  rowItem,
  runConversationLabels,
} from "../helpers/runConversations";
import {
  ConversationCheckRow,
  DatasetFact,
  TurnCheckRow,
  Fact,
  HeaderCard,
  PendingRulesNote,
  type RunContext,
  VerdictIcon,
  VerdictStats,
  WorkflowFact,
} from "./resultsParts";
import { useRunConversations } from "../hooks/useRunConversations";
import { MARK, MARKED, useTurnJump } from "../hooks/useTurnJump";
import { isRunInProgress, runDate, runName } from "../helpers/runResults";
import { TurnStepsDialog } from "./TurnStepsDialog";
import { AgentReply, CustomerBubble, TurnChecksDialog } from "./conversationParts";

const STATUS_ORDER = ["failed", "not_evaluated", "passed"];

/** Checks on one turn each, all shown, failed first, each with a link to its turn. */
export const TurnChecksCard: React.FC<{
  rows: { item: GradedItem; turn: number }[];
  onJump?: (turn: number) => void;
}> = ({ rows, onJump }) => {
  const ordered = [...rows].sort(
    (a, b) => STATUS_ORDER.indexOf(a.item.status) - STATUS_ORDER.indexOf(b.item.status) || a.turn - b.turn,
  );
  return (
    <section className="space-y-3 rounded-lg border bg-card p-4">
      <h2 className="font-semibold">Turn checks</h2>
      {ordered.length ? (
        <div className="space-y-3">
          {ordered.map(({ item, turn }) => (
            <TurnCheckRow key={`${item.key}-${turn}`} item={item} turn={turn} onJump={onJump} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No checks.</p>
      )}
    </section>
  );
};

/** Checks on the whole conversation, all shown, failed first, each with the turns to look at. */
export const WholeConversationChecks: React.FC<{
  items: GradedItem[];
  turnCount: number;
  onJump?: (turn: number) => void;
  className?: string;
}> = ({ items, turnCount, onJump, className }) => {
  const ordered = [...items].sort((a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status));
  return (
    <section className={cn("space-y-3 rounded-lg border bg-card p-4", className)}>
      <h2 className="font-semibold">Whole conversation</h2>
      {ordered.length ? (
        <div className="space-y-3">
          {ordered.map((item) => (
            <ConversationCheckRow key={item.key} item={item} turnCount={turnCount} onJump={onJump} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No checks.</p>
      )}
    </section>
  );
};

export interface ConversationResultViewProps {
  run: TestRun;
  context?: RunContext;
  conversationKey: string;
  /** Names where Back goes, when not to the run. */
  backLabel?: string;
  onBack: () => void;
  onNavigate: (key: string) => void;
}

/** One conversation of a run as a chat: each reply with its verdict, and its steps and checks a click away. */
export const ConversationResultView: React.FC<ConversationResultViewProps> = ({
  run,
  context = {},
  conversationKey,
  backLabel: backTo,
  onBack,
  onNavigate,
}) => {
  const [stepsFor, setStepsFor] = useState<RunTurnResult | null>(null);
  const [checksFor, setChecksFor] = useState<RunTurnResult | null>(null);
  const { data, isLoading, isError } = useRunConversations(run);
  const labels = useMemo(() => runConversationLabels(data?.conversations ?? []), [data]);
  const ordered = useMemo(() => reviewOrder(data?.conversations ?? []), [data]);
  const index = ordered.findIndex((entry) => entry.key === conversationKey);
  const conversation = ordered[index];
  const previous = index > 0 ? ordered[index - 1] : null;
  const next = index >= 0 && index < ordered.length - 1 ? ordered[index + 1] : null;
  const backLabel = backTo ?? `Back to ${runName(run)}`;
  const { jump, ref, marked } = useTurnJump();

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-80" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (isError || !data || !conversation) {
    return (
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={onBack} aria-label={backLabel}>
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <p className={cn("text-sm", isError || !data ? "text-destructive" : "text-muted-foreground")}>
          {isError || !data ? "The results could not be loaded." : "This conversation is not in the run."}
        </p>
      </div>
    );
  }

  const label = labels.get(conversation.key) ?? conversation.key;
  const turns = conversation.turns.length;
  const counts = conversationCheckCounts(conversation);
  const turnRows = turnCheckRows(conversation);
  const jumpToTurn = (number: number) => {
    const key = conversation.turns.find((turn) => turn.number === number)?.case_id;
    if (key) jump(key);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start gap-2">
        <Button variant="ghost" size="icon" onClick={onBack} className="shrink-0" aria-label={backLabel}>
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <div className="flex min-w-0 flex-1 items-center gap-2 self-center">
          <VerdictIcon verdict={conversation.verdict} className="h-5 w-5" />
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
        <HeaderCard outcome={counts.total > 0 ? <VerdictStats counts={counts} noun="Checks" /> : undefined}>
          <WorkflowFact run={run} context={context} />
          <DatasetFact run={run} context={context} />
          <Fact label="Run">{runName(run)}</Fact>
          <Fact label="Turns">
            {turns} turn{turns === 1 ? "" : "s"}
          </Fact>
          <Fact label="Ran on" note={isRunInProgress(run) ? "Still running" : undefined}>
            {runDate(run)}
          </Fact>
        </HeaderCard>

        <PendingRulesNote run={run} pending={data.rules_pending} />

        {/* Side by side: the whole conversation's checks on the left, the turns' on the right. */}
        <div className="grid items-start gap-6 lg:grid-cols-2">
          <WholeConversationChecks items={conversation.rules.map(rowItem)} turnCount={turns} onJump={jumpToTurn} />
          <TurnChecksCard rows={turnRows} onJump={jumpToTurn} />
        </div>

        <div className="space-y-6 rounded-lg border bg-card p-4 sm:p-6">
          {conversation.turns.map((turn) => (
            <div
              key={turn.case_id}
              ref={ref(turn.case_id)}
              className={cn("space-y-3", MARK, marked === turn.case_id && MARKED)}
            >
              <CustomerBubble message={turn.message} />
              <AgentReply
                turn={turn}
                conversation={conversation}
                onShowSteps={() => setStepsFor(turn)}
                onShowChecks={() => setChecksFor(turn)}
              />
              {!turn.in_dataset && (
                <p className="text-right text-xs text-muted-foreground">This turn was removed from the dataset since.</p>
              )}
            </div>
          ))}
        </div>
      </div>

      {stepsFor && run.id && (
        <TurnStepsDialog
          open={Boolean(stepsFor)}
          onOpenChange={(open) => !open && setStepsFor(null)}
          runId={run.id}
          caseId={stepsFor.case_id}
          workflowId={run.workflow_id}
          runCreatedAt={run.created_at}
          title="Steps"
          description={`How the workflow answered “${excerpt(stepsFor.message)}”. Select a step to see what went in and what came out.`}
        />
      )}
      {checksFor && (
        <TurnChecksDialog turn={checksFor} conversation={conversation} onClose={() => setChecksFor(null)} />
      )}
    </div>
  );
};
