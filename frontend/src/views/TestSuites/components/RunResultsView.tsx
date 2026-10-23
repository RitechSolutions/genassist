import React, { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, GitCompareArrows, Loader2 } from "lucide-react";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Skeleton } from "@/components/skeleton";
import type { RunConversationResult, RunConversations, TestRun } from "@/interfaces/testSuite.interface";
import {
  conversationFindings,
  notEvaluatedReason,
  rowItem,
  runCheckCount,
  runChecks,
  runConversationLabels,
} from "../helpers/runConversations";
import type { CheckConversation } from "../helpers/checks";
import {
  checksGradingError,
  isRunInProgress,
  runDate,
  runDuration,
  runFailureText,
  runName,
  runProgressText,
} from "../helpers/runResults";
import { useRunConversations } from "../hooks/useRunConversations";
import { ChecksDialog } from "./ChecksDialog";
import {
  DatasetFact,
  Fact,
  GradedItemRow,
  HeaderCard,
  PendingRulesNote,
  type RunContext,
  VerdictIcon,
  VerdictStats,
  WorkflowFact,
} from "./resultsParts";

const plural = (count: number, noun: string) => `${count} ${noun}${count === 1 ? "" : "s"}`;

export const RunHeading: React.FC<{ run: TestRun; title?: string }> = ({ run, title }) => (
  <div className="flex min-w-0 flex-wrap items-center gap-2">
    <h1 className="truncate text-2xl font-bold tracking-tight">{title ?? runName(run)}</h1>
    {isRunInProgress(run) && (
      <Badge variant="outline" className="flex items-center gap-1">
        <Loader2 className="h-3 w-3 animate-spin" />
        Running
      </Badge>
    )}
  </div>
);

/** How its conversations went, large, on the left; what the run played and when on the right. */
const RunSummaryCard: React.FC<{
  run: TestRun;
  data?: RunConversations;
  loading: boolean;
  context: RunContext;
  onShowChecks: () => void;
}> = ({ run, data, loading, context, onShowChecks }) => {
  const duration = runDuration(run);
  const counts = data?.counts;
  const checks = data ? runCheckCount(data) : null;
  // Counts come from results, so a run without any would read "0 checks" and "0 conversations".
  const graded = !counts || counts.total > 0;
  const noChecks = loading ? "…" : "–";
  // Results that could not load leave the outcome empty; the page says why below.
  const outcome = loading ? (
    <>
      <Skeleton className="h-12 w-20" />
      <Skeleton className="h-12 w-20" />
    </>
  ) : counts && counts.total > 0 ? (
    <VerdictStats counts={counts} />
  ) : null;
  return (
    <HeaderCard outcome={outcome}>
      <WorkflowFact run={run} context={context} />
      <DatasetFact
        run={run}
        context={context}
        note={counts && graded ? plural(counts.total, "conversation") : undefined}
      />
      {graded && (
        <Fact label="Checks">
          {checks === null ? (
            noChecks
          ) : (
            <>
              {plural(checks, "check")}
              {checks > 0 && (
                <button
                  type="button"
                  onClick={onShowChecks}
                  aria-haspopup="dialog"
                  className="ml-2 text-xs font-medium text-primary hover:underline"
                >
                  Show
                </button>
              )}
            </>
          )}
        </Fact>
      )}
      <Fact label="Ran on">{runDate(run)}</Fact>
      <Fact label="Duration">{duration ?? (isRunInProgress(run) ? "Still running" : "Unknown")}</Fact>
    </HeaderCard>
  );
};

const ConversationRow: React.FC<{
  conversation: RunConversationResult;
  label: string;
  gradingError: string | null;
  onOpen: () => void;
}> = ({ conversation, label, gradingError, onOpen }) => {
  const findings = conversation.verdict === "failed" ? conversationFindings(conversation) : [];
  const reason = conversation.verdict === "not_evaluated" ? notEvaluatedReason(conversation, gradingError) : null;
  const turns = conversation.turns.length;
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex w-full items-center gap-3 rounded-lg border bg-card p-3 text-left transition-colors hover:bg-muted"
    >
      <VerdictIcon verdict={conversation.verdict} />
      <div className="min-w-0 flex-1 space-y-0.5">
        <div className="truncate font-medium">{label}</div>
        {/* The first failed check, and a pill counting the rest so it does not read as part of the sentence. */}
        {findings.length > 0 && (
          <p className="flex min-w-0 items-center gap-2 text-sm text-muted-foreground">
            <span className="truncate">{findings[0]}</span>
            {findings.length > 1 && (
              // A see-through grey, so it stays darker than the row on hover too.
              <span className="shrink-0 rounded-full bg-foreground/5 px-2 py-0.5 text-[11px] font-medium text-foreground/60">
                +{findings.length - 1} more
              </span>
            )}
          </p>
        )}
        {reason && <p className="truncate text-sm text-muted-foreground">{reason}</p>}
      </div>
      <span className="shrink-0 text-xs text-muted-foreground">
        {turns} turn{turns === 1 ? "" : "s"}
      </span>
      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
    </button>
  );
};

// Every section stays open, so a run where all passed still lists its conversations.
const Section: React.FC<{ title: string; count: number; children: React.ReactNode }> = ({ title, count, children }) => {
  if (!count) return null;
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold">
        {title} {count}
      </h2>
      <div className="space-y-2">{children}</div>
    </section>
  );
};

export interface RunResultsViewProps {
  run: TestRun;
  context?: RunContext;
  /** The dataset's conversations, to place the run's checks. */
  conversations?: CheckConversation[];
  conversationsReady?: boolean;
  backLabel: string;
  onBack: () => void;
  onOpenConversation: (key: string) => void;
  /** Opens the comparison with this run picked; left out when there is no other run to compare with. */
  onCompare?: () => void;
}

/** A run's results by conversation: the verdict first, then what failed, what was not evaluated, and what passed. */
export const RunResultsView: React.FC<RunResultsViewProps> = ({
  run,
  context = {},
  conversations = [],
  conversationsReady = false,
  backLabel,
  onBack,
  onOpenConversation,
  onCompare,
}) => {
  const { data, isLoading, isError } = useRunConversations(run);
  const labels = useMemo(() => runConversationLabels(data?.conversations ?? []), [data]);
  const byVerdict = (verdict: string) => (data?.conversations ?? []).filter((entry) => entry.verdict === verdict);
  const failed = byVerdict("failed");
  const notEvaluated = byVerdict("not_evaluated");
  const passed = byVerdict("passed");
  const gradingError = checksGradingError(run);
  const [showChecks, setShowChecks] = useState(false);
  const checks = useMemo(() => (data ? runChecks(data) : []), [data]);
  const row = (conversation: RunConversationResult) => (
    <ConversationRow
      key={conversation.key}
      conversation={conversation}
      label={labels.get(conversation.key) ?? conversation.key}
      gradingError={gradingError}
      onOpen={() => onOpenConversation(conversation.key)}
    />
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start gap-2">
        <Button variant="ghost" size="icon" onClick={onBack} className="shrink-0" aria-label={backLabel}>
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <div className="min-w-0 flex-1">
          <RunHeading run={run} />
        </div>
        {run.status === "completed" && onCompare && (
          <Button variant="outline" onClick={onCompare} icon={<GitCompareArrows className="h-4 w-4" />}>
            Compare
          </Button>
        )}
      </div>

      <RunSummaryCard
        run={run}
        data={data}
        loading={isLoading}
        context={context}
        onShowChecks={() => setShowChecks(true)}
      />
      <ChecksDialog
        open={showChecks}
        onOpenChange={setShowChecks}
        checks={checks}
        description={`The checks as ${runName(run)} graded them.`}
        conversations={conversations}
        conversationsReady={conversationsReady}
      />

      {run.status === "failed" && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
          {runFailureText(run)}
        </div>
      )}

      {isRunInProgress(run) && (
        <p className="text-sm text-muted-foreground">{runProgressText(run) ?? "Waiting to start…"}</p>
      )}

      {gradingError && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-300">
          {gradingError}
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-7 w-40" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : isError || !data ? (
        <p className="text-sm text-destructive">The results could not be loaded.</p>
      ) : data.counts.total === 0 ? (
        // A failed run already says why above.
        run.status !== "failed" && (
          <p className="text-sm text-muted-foreground">
            {isRunInProgress(run) ? "No conversation has finished yet." : "This run has no results."}
          </p>
        )
      ) : (
        <>
          <PendingRulesNote run={run} pending={data.rules_pending} />

          <Section title="Failed" count={failed.length}>
            {failed.map(row)}
          </Section>
          <Section title="Not evaluated" count={notEvaluated.length}>
            {notEvaluated.map(row)}
          </Section>
          <Section title="Passed" count={passed.length}>
            {passed.map(row)}
          </Section>
          <Section title="Checks with no conversation in this run" count={data.other_rules.length}>
            <div className="space-y-3 rounded-lg border bg-card p-3">
              {data.other_rules.map((rule) => (
                <GradedItemRow key={rule.id} item={rowItem(rule)} />
              ))}
            </div>
          </Section>
        </>
      )}
    </div>
  );
};
