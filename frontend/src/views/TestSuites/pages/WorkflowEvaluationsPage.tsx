import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, GitBranch, ListChecks, Loader2, Play, Search } from "lucide-react";
import toast from "react-hot-toast";

import { PageLayout } from "@/components/PageLayout";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { PaginationBar } from "@/components/PaginationBar";
import { PageListSkeleton } from "@/components/skeletons";
import { TooltipProvider } from "@/components/RadixTooltip";
import { TooltipButton } from "@/components/tooltip-button";

import { getWorkflowsMinimal } from "@/services/workflows";
import { getTestRunsBatch, listTestSuites } from "@/services/testSuites";
import { getLLMProvidersMinimal } from "@/services/llmProviders";
import {
  deleteTestEvaluation,
  getWorkflowEvaluationsPage,
  runTestEvaluation,
  runWorkflowEvaluations,
  updateTestEvaluation,
} from "@/services/testEvaluations";
import { TestEvaluationConfig } from "@/interfaces/testEvaluation.interface";
import { WorkflowMinimal } from "@/interfaces/workflow.interface";
import { TestRun, TestSuite } from "@/interfaces/testSuite.interface";
import { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";
import { EvaluationWizard, EvaluationWizardData } from "../components/EvaluationWizard";
import { EvaluationListRow } from "../components/EvaluationListRow";
import { RunAgainstVersionDialog } from "../components/RunAgainstVersionDialog";
import { buildTechniqueConfigs, getEditInitialData, wizardMetadata } from "../helpers/evaluationForm";

const PAGE_SIZE = 20;
const UNASSIGNED = "unassigned";
const RUNNING_POLL_MS = 5000;

const WorkflowEvaluationsPage: React.FC = () => {
  const navigate = useNavigate();
  const { workflowId = "" } = useParams();
  const isUnassigned = workflowId === UNASSIGNED;

  const [workflows, setWorkflows] = useState<WorkflowMinimal[]>([]);
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [providers, setProviders] = useState<LLMProviderMinimal[]>([]);

  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");

  const [lastRunsByEvaluationId, setLastRunsByEvaluationId] = useState<
    Record<string, TestRun | null>
  >({});
  const [runningEvalIds, setRunningEvalIds] = useState<Set<string>>(new Set());
  const [isWorkflowRunning, setIsWorkflowRunning] = useState(false);
  const [workflowProgress, setWorkflowProgress] = useState<{ done: number; total: number } | null>(
    null,
  );
  // Synchronous guard against a rapid double-click (state updates are async).
  const isRunAllInFlight = useRef(false);
  const runAllPollTimer = useRef<number | null>(null);
  // Bumped whenever the Run-all poll must be abandoned (unmount or workflow switch)
  // so an in-flight poll from a previous context can't apply to the current one.
  const runAllEpoch = useRef(0);
  const isMounted = useRef(true);

  // Set true on setup so React Strict Mode's setup/cleanup/setup cycle leaves it true.
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  // React Router reuses this component across workflows, so when the id changes
  // abandon the previous workflow's Run-all poll and reset its guard/progress —
  // otherwise workflow A's poll could land on workflow B's page.
  useEffect(() => {
    return () => {
      runAllEpoch.current += 1;
      if (runAllPollTimer.current) {
        window.clearTimeout(runAllPollTimer.current);
        runAllPollTimer.current = null;
      }
      isRunAllInFlight.current = false;
      setIsWorkflowRunning(false);
      setWorkflowProgress(null);
    };
  }, [workflowId]);

  const [editingEvaluation, setEditingEvaluation] = useState<TestEvaluationConfig | null>(null);
  const [deletingEvaluationId, setDeletingEvaluationId] = useState<string | null>(null);
  const [isRunAllVersionDialogOpen, setIsRunAllVersionDialogOpen] = useState(false);

  // staleTime 0 makes react-query refetch this when the tab regains focus. The
  // interval is the page's only poll: it runs when a batch is active that this
  // session isn't already tracking, and react-query pauses it in a hidden tab.
  const {
    data: pageData = null,
    dataUpdatedAt,
    isPending: isLoading,
    isError: hasError,
    refetch: refetchPage,
  } = useQuery({
    queryKey: ["workflow-evaluations", workflowId, page, search],
    queryFn: async () =>
      (await getWorkflowEvaluationsPage(workflowId, {
        page,
        pageSize: PAGE_SIZE,
        search,
      })) ?? null,
    staleTime: 0,
    refetchInterval: (query) =>
      query.state.data?.any_running && !isWorkflowRunning ? RUNNING_POLL_MS : false,
  });

  const evaluations = pageData?.items ?? [];
  const total = pageData?.total ?? 0;
  const totalUnfiltered = pageData?.total_unfiltered ?? 0;
  const currentWorkflow = workflows.find((w) => w.id === workflowId);
  const workflowName = isUnassigned
    ? "Unassigned evaluations"
    : currentWorkflow?.name ?? "Workflow";
  const workflowAgentId = isUnassigned ? null : currentWorkflow?.agent_id ?? null;
  // Offered on every workflow; the dialog handles one with no second version.
  const canRunAgainstVersion = Boolean(workflowAgentId);

  useEffect(() => {
    const load = async () => {
      const [workflowData, suiteData, providersData] = await Promise.all([
        getWorkflowsMinimal(),
        listTestSuites(),
        getLLMProvidersMinimal(),
      ]);
      setWorkflows(workflowData ?? []);
      setSuites(suiteData ?? []);
      setProviders((providersData ?? []).filter((p) => p.is_active === 1));
    };
    void load();
  }, []);

  // Debounce the search box and reset to the first page when it changes.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  // Load the latest run for each evaluation on the page.
  useEffect(() => {
    const loadLastRuns = async () => {
      const items = pageData?.items ?? [];
      const runIdToEvalId: Record<string, string> = {};
      items.forEach((evaluation) => {
        const lastRunId = evaluation.run_ids?.[0];
        if (evaluation.id && lastRunId) runIdToEvalId[lastRunId] = evaluation.id;
      });
      const runIds = Object.keys(runIdToEvalId);
      if (!runIds.length) {
        setLastRunsByEvaluationId({});
        return;
      }
      try {
        const runs = await getTestRunsBatch(runIds);
        const mapping: Record<string, TestRun | null> = {};
        (runs ?? []).forEach((run) => {
          const evalId = run.id ? runIdToEvalId[run.id] : undefined;
          if (evalId) mapping[evalId] = run;
        });
        setLastRunsByEvaluationId(mapping);
      } catch {
        setLastRunsByEvaluationId({});
      }
    };
    void loadLastRuns();
    // Keyed on dataUpdatedAt, not pageData: react-query's structural sharing keeps
    // the same object reference when a poll returns identical rows, but run status
    // lives in test_runs — so it must refresh on every fetch, not only on change.
  }, [dataUpdatedAt]);

  const isEvaluationRunning = (evaluation: TestEvaluationConfig): boolean => {
    if (evaluation.id && runningEvalIds.has(evaluation.id)) return true;
    const lastRun = evaluation.id ? lastRunsByEvaluationId[evaluation.id] : null;
    return lastRun?.status === "queued" || lastRun?.status === "running";
  };

  const getAverageAccuracy = (evaluation: TestEvaluationConfig): number | null => {
    const lastRun = evaluation.id ? lastRunsByEvaluationId[evaluation.id] : null;
    if (!lastRun?.summary_metrics) return null;
    const metrics = lastRun.summary_metrics as Record<string, { accuracy?: number }>;
    const accuracies = Object.values(metrics)
      .map((m) => m.accuracy)
      .filter((a): a is number => typeof a === "number");
    if (!accuracies.length) return null;
    return accuracies.reduce((sum, a) => sum + a, 0) / accuracies.length;
  };

  const handleQuickRun = async (evaluation: TestEvaluationConfig, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!evaluation.id || isEvaluationRunning(evaluation)) return;
    setRunningEvalIds((prev) => new Set(prev).add(evaluation.id));
    try {
      const created = await runTestEvaluation(evaluation.id);
      if (created?.id) {
        setLastRunsByEvaluationId((prev) => ({ ...prev, [evaluation.id as string]: created }));
        toast.success("Evaluation started");
        void refetchPage(); // any_running turns on, which starts the status poll
      }
    } catch (error) {
      if (isRunningConflict(error)) {
        toast.error("This evaluation is already running");
        void refetchPage();
      } else {
        toast.error("Failed to start evaluation");
      }
    } finally {
      setRunningEvalIds((prev) => {
        const next = new Set(prev);
        if (evaluation.id) next.delete(evaluation.id);
        return next;
      });
    }
  };

  const handleRunAll = async (targetWorkflowId?: string) => {
    if (isUnassigned || isRunAllInFlight.current || isWorkflowRunning || pageData?.any_running) {
      return;
    }
    isRunAllInFlight.current = true;
    const epoch = runAllEpoch.current; // invalidated if the workflow changes
    setIsWorkflowRunning(true);
    setWorkflowProgress(null); // real total is known only once runs are started
    const isStale = () => !isMounted.current || epoch !== runAllEpoch.current;
    const finish = () => {
      if (isStale()) return; // don't touch another workflow's guard/progress
      isRunAllInFlight.current = false;
      setIsWorkflowRunning(false);
      void refetchPage(); // settle any_running/health once the batch ends
    };

    try {
      const started = await runWorkflowEvaluations(workflowId, targetWorkflowId);
      if (isStale()) return; // navigated away before the POST resolved
      const startedRuns = (started ?? []).filter(
        (s): s is typeof s & { run_id: string } => Boolean(s.run_id),
      );
      const failedCount = (started ?? []).length - startedRuns.length;
      if (!startedRuns.length) {
        toast.error("No evaluations could be started");
        finish();
        return;
      }
      if (failedCount > 0) {
        toast.error(`${failedCount} evaluation${failedCount !== 1 ? "s" : ""} failed to start`);
      }
      const runIdToEvalId: Record<string, string> = {};
      startedRuns.forEach((s) => {
        runIdToEvalId[s.run_id] = s.evaluation_id;
      });
      const runIds = startedRuns.map((s) => s.run_id);
      // Run all starts every evaluation in the workflow, not just the filtered page.
      setWorkflowProgress({ done: 0, total: runIds.length });
      toast.success(`Started ${runIds.length} evaluation${runIds.length !== 1 ? "s" : ""}`);

      let consecutivePollErrors = 0;
      const maxPollErrors = 5;
      const poll = async () => {
        if (isStale()) return;
        // Don't poll a hidden tab; pick back up on the next tick.
        if (document.visibilityState !== "visible") {
          runAllPollTimer.current = window.setTimeout(poll, RUNNING_POLL_MS);
          return;
        }
        try {
          const runs = await getTestRunsBatch(runIds);
          consecutivePollErrors = 0;
          const updates: Record<string, TestRun> = {};
          let done = 0;
          (runs ?? []).forEach((run) => {
            if (!run?.id) return;
            const evalId = runIdToEvalId[run.id];
            if (evalId) updates[evalId] = run;
            if (run.status === "completed" || run.status === "failed") done += 1;
          });
          if (isStale()) return;
          setLastRunsByEvaluationId((prev) => ({ ...prev, ...updates }));
          setWorkflowProgress({ done, total: runIds.length });
          if (done >= runIds.length) {
            finish();
            return;
          }
        } catch {
          consecutivePollErrors += 1;
          if (consecutivePollErrors >= maxPollErrors) {
            toast.error("Lost track of running evaluations. Refresh to see their status.");
            finish();
            return;
          }
        }
        if (!isStale()) runAllPollTimer.current = window.setTimeout(poll, RUNNING_POLL_MS);
      };
      runAllPollTimer.current = window.setTimeout(poll, 2000);
    } catch (error) {
      if (isStale()) return; // navigated away before the POST rejected
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        toast.error("This workflow already has running evaluations");
        void refetchPage(); // refetch so any_running blocks the button
      } else {
        toast.error("Failed to start evaluations");
      }
      finish();
    }
  };

  // The backend refuses (409) if the evaluation started running since the page
  // loaded, so a stale UI can't edit or delete a run in flight.
  const isRunningConflict = (error: unknown): boolean =>
    (error as { response?: { status?: number } })?.response?.status === 409;

  const handleEditSubmit = async (data: EvaluationWizardData) => {
    if (!editingEvaluation?.id) return;
    try {
      const updated = await updateTestEvaluation(editingEvaluation.id, {
        name: data.name.trim(),
        description: data.description.trim() || undefined,
        suite_id: data.suiteId,
        workflow_id: data.workflowId === "none" ? undefined : data.workflowId,
        techniques: data.metrics,
        technique_configs: buildTechniqueConfigs(data),
        input_metadata: wizardMetadata(data),
      });
      if (!updated) return;
      setEditingEvaluation(null);
      toast.success("Evaluation updated");
      void refetchPage(); // its workflow may have changed — refetch the page
    } catch (error) {
      if (isRunningConflict(error)) {
        toast.error("This evaluation is running. Wait for it to finish before editing.");
        setEditingEvaluation(null);
        void refetchPage();
      } else {
        toast.error("Failed to update evaluation");
      }
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteTestEvaluation(id);
    } catch (error) {
      setDeletingEvaluationId(null);
      if (isRunningConflict(error)) {
        toast.error("This evaluation is running. Wait for it to finish before deleting.");
        void refetchPage();
      } else {
        toast.error("Failed to delete evaluation");
      }
      return;
    }
    setDeletingEvaluationId(null);
    toast.success("Evaluation deleted");
    if (evaluations.length === 1 && page > 1) {
      setPage((current) => current - 1);
    } else {
      void refetchPage();
    }
  };

  return (
    <PageLayout>
      <div className="mb-6 flex flex-wrap items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate("/tests/evaluations")}
          className="shrink-0"
          aria-label="Back to evaluations"
        >
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <div className="flex items-center gap-2 min-w-0">
          <h1 className="text-2xl font-bold tracking-tight truncate animate-fade-down">
            {workflowName}
          </h1>
          <Badge variant="secondary" className="shrink-0">
            {search
              ? `Showing ${total} of ${totalUnfiltered}`
              : `${total} evaluation${total !== 1 ? "s" : ""}`}
          </Badge>
        </div>
        <div className="ml-auto flex items-center gap-2 shrink-0">
          <div className="relative w-56">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search evaluations..."
              className="w-full pl-9 pr-3 py-2 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          {!isUnassigned && (
            <div className="flex items-center gap-2">
              {canRunAgainstVersion && (
                <TooltipProvider delayDuration={200}>
                  <TooltipButton
                    button={
                      <Button
                        variant="outline"
                        size="icon"
                        disabled={isWorkflowRunning || Boolean(pageData?.any_running)}
                        onClick={() => setIsRunAllVersionDialogOpen(true)}
                        aria-label="Run all against a version"
                      >
                        <GitBranch className="h-4 w-4" />
                      </Button>
                    }
                    tooltipContent={{ children: <p>Run all against a version</p> }}
                  />
                </TooltipProvider>
              )}
              <Button
                variant="outline"
                disabled={isWorkflowRunning || Boolean(pageData?.any_running)}
                onClick={() => handleRunAll()}
              >
                {isWorkflowRunning && workflowProgress ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    {workflowProgress.done}/{workflowProgress.total}
                  </>
                ) : isWorkflowRunning ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    Starting…
                  </>
                ) : pageData?.any_running ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    Running…
                  </>
                ) : (
                  <>
                    <Play className="h-3.5 w-3.5 mr-1" />
                    Run all
                  </>
                )}
              </Button>
            </div>
          )}
        </div>
      </div>

      <div className="rounded-lg border bg-card dark:bg-zinc-900 overflow-hidden">
        {isLoading ? (
          <PageListSkeleton variant="evaluation" bordered={false} />
        ) : hasError ? (
          <div className="py-16 text-center">
            <p className="text-sm text-muted-foreground mb-3">Couldn't load evaluations.</p>
            <Button variant="outline" onClick={() => void refetchPage()}>
              Retry
            </Button>
          </div>
        ) : evaluations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
            <div className="rounded-full bg-muted p-4">
              <ListChecks className="h-10 w-10 text-muted-foreground" />
            </div>
            <p className="text-sm text-muted-foreground max-w-sm">
              {search
                ? "No evaluations match your search."
                : "This workflow has no evaluations yet. Create one from the Evaluations overview."}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {evaluations.map((evaluation) => (
              <EvaluationListRow
                key={evaluation.id}
                evaluation={evaluation}
                avgAccuracy={getAverageAccuracy(evaluation)}
                isRunning={isEvaluationRunning(evaluation)}
                lastRunStatus={
                  evaluation.id ? lastRunsByEvaluationId[evaluation.id]?.status : undefined
                }
                onOpen={() => navigate(`/tests/evaluations/${evaluation.id}`)}
                onEdit={() => setEditingEvaluation(evaluation)}
                onDelete={() => setDeletingEvaluationId(evaluation.id ?? null)}
                onRun={(e) => handleQuickRun(evaluation, e)}
              />
            ))}
          </div>
        )}
      </div>

      {!isLoading && !hasError && total > PAGE_SIZE && (
        <PaginationBar
          total={total}
          currentPage={page}
          pageSize={PAGE_SIZE}
          pageItemCount={evaluations.length}
          onPageChange={setPage}
          className="mt-4"
        />
      )}

      {canRunAgainstVersion && workflowAgentId && (
        <RunAgainstVersionDialog
          isOpen={isRunAllVersionDialogOpen}
          onOpenChange={setIsRunAllVersionDialogOpen}
          agentId={workflowAgentId}
          currentWorkflowId={workflowId}
          workflowName={workflowName}
          confirmLabel="Run all"
          isStarting={isWorkflowRunning}
          onRun={(targetWorkflowId) => {
            setIsRunAllVersionDialogOpen(false);
            void handleRunAll(targetWorkflowId);
          }}
        />
      )}

      {editingEvaluation && (
        <EvaluationWizard
          isOpen={!!editingEvaluation}
          onOpenChange={(open) => {
            if (!open) setEditingEvaluation(null);
          }}
          onSubmit={handleEditSubmit}
          suites={suites}
          workflows={workflows}
          providers={providers}
          mode="edit"
          initialData={getEditInitialData(editingEvaluation, providers)}
        />
      )}

      <Dialog
        open={!!deletingEvaluationId}
        onOpenChange={(open) => {
          if (!open) setDeletingEvaluationId(null);
        }}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Evaluation</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete this evaluation? This will also permanently delete all
            associated runs and their results. This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeletingEvaluationId(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deletingEvaluationId && handleDelete(deletingEvaluationId)}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageLayout>
  );
};

export default WorkflowEvaluationsPage;
