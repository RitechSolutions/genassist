import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ChevronRight, Layers, ListChecks, Loader2, Play, Plus } from "lucide-react";
import toast from "react-hot-toast";

import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { PageListSkeleton } from "@/components/skeletons";
import { cn } from "@/lib/utils";

import { getWorkflowsMinimal } from "@/services/workflows";
import { listTestSuites } from "@/services/testSuites";
import { getLLMProvidersMinimal } from "@/services/llmProviders";
import {
  createTestEvaluation,
  getWorkflowEvaluationSummaries,
  runWorkflowEvaluations,
  WorkflowEvaluationSummary,
} from "@/services/testEvaluations";
import { WorkflowMinimal } from "@/interfaces/workflow.interface";
import { TestSuite } from "@/interfaces/testSuite.interface";
import { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";
import { EvaluationWizard, EvaluationWizardData } from "../components/EvaluationWizard";
import { EntityTitle } from "../components/EntityTitle";
import { buildTechniqueConfigs, wizardMetadata } from "../helpers/evaluationForm";
import { accuracyColorClass } from "../helpers/evaluationMetrics";

const UNASSIGNED = "unassigned";
const SUMMARIES_QUERY_KEY = ["workflow-evaluation-summaries"];
const RUNNING_POLL_MS = 5000;

interface WorkflowRow {
  key: string;
  workflowId: string | null;
  name: string;
  count: number;
  health: number | null;
  finishedCount: number;
  anyRunning: boolean;
  isUnassigned: boolean;
}

const EvaluationsPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [workflows, setWorkflows] = useState<WorkflowMinimal[]>([]);
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [providers, setProviders] = useState<LLMProviderMinimal[]>([]);
  const [isReferenceLoading, setIsReferenceLoading] = useState(true);
  const [hasReferenceError, setHasReferenceError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [runningWorkflowIds, setRunningWorkflowIds] = useState<Set<string>>(new Set());
  // Synchronous guard against rapid double-clicks (state updates are async).
  const inFlightWorkflowIds = useRef<Set<string>>(new Set());

  // Summaries carry the live health and running state. staleTime 0 makes
  // react-query refetch them when the tab regains focus; the interval only runs
  // while a batch is active and react-query pauses it in a hidden tab.
  const {
    data: summaries = [],
    isPending: isSummariesLoading,
    isError: hasSummariesError,
    refetch: refetchSummaries,
  } = useQuery({
    queryKey: SUMMARIES_QUERY_KEY,
    queryFn: async () => (await getWorkflowEvaluationSummaries()) ?? [],
    staleTime: 0,
    refetchInterval: (query) =>
      (query.state.data ?? []).some((summary) => summary.any_running)
        ? RUNNING_POLL_MS
        : false,
  });

  const isLoading = isSummariesLoading || isReferenceLoading;
  const hasError = hasSummariesError || hasReferenceError;

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setIsReferenceLoading(true);
      setHasReferenceError(false);
      try {
        const [workflowData, suiteData, providersData] = await Promise.all([
          getWorkflowsMinimal(),
          listTestSuites(),
          getLLMProvidersMinimal(),
        ]);
        if (cancelled) return;
        setWorkflows(workflowData ?? []);
        setSuites(suiteData ?? []);
        setProviders((providersData ?? []).filter((p) => p.is_active === 1));
      } catch {
        if (!cancelled) setHasReferenceError(true);
      } finally {
        if (!cancelled) setIsReferenceLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const rows = useMemo<WorkflowRow[]>(() => {
    const nameFor = (workflowId: string | null): string => {
      if (workflowId === null) return "Unassigned evaluations";
      return workflows.find((w) => w.id === workflowId)?.name ?? "Unknown workflow";
    };
    const query = searchQuery.trim().toLowerCase();
    return summaries
      .map((summary) => ({
        key: summary.workflow_id ?? UNASSIGNED,
        workflowId: summary.workflow_id,
        name: nameFor(summary.workflow_id),
        count: summary.eval_count,
        health: summary.health,
        finishedCount: summary.finished_count,
        anyRunning: summary.any_running,
        isUnassigned: summary.workflow_id === null,
      }))
      .filter((row) => !query || row.name.toLowerCase().includes(query))
      .sort((a, b) => {
        if (a.isUnassigned) return 1;
        if (b.isUnassigned) return -1;
        return a.name.localeCompare(b.name);
      });
  }, [summaries, workflows, searchQuery]);

  const openWorkflow = (row: WorkflowRow) => {
    navigate(`/tests/evaluations/workflows/${row.workflowId ?? UNASSIGNED}`);
  };

  const markWorkflowRunning = (workflowId: string) => {
    queryClient.setQueryData<WorkflowEvaluationSummary[]>(SUMMARIES_QUERY_KEY, (prev) =>
      (prev ?? []).map((summary) =>
        summary.workflow_id === workflowId ? { ...summary, any_running: true } : summary,
      ),
    );
  };

  const handleRunAll = async (workflowId: string) => {
    if (inFlightWorkflowIds.current.has(workflowId)) return;
    inFlightWorkflowIds.current.add(workflowId);
    setRunningWorkflowIds((prev) => new Set(prev).add(workflowId));
    try {
      const started = await runWorkflowEvaluations(workflowId);
      const startedCount = (started ?? []).filter((s) => s.run_id).length;
      if (!startedCount) {
        toast.error("No evaluations could be started for this workflow");
      } else {
        toast.success(`Started ${startedCount} evaluation${startedCount !== 1 ? "s" : ""}`);
        markWorkflowRunning(workflowId);
      }
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        toast.error("This workflow already has running evaluations");
        markWorkflowRunning(workflowId);
      } else {
        toast.error("Failed to start evaluations for this workflow");
      }
    } finally {
      inFlightWorkflowIds.current.delete(workflowId);
      setRunningWorkflowIds((prev) => {
        const next = new Set(prev);
        next.delete(workflowId);
        return next;
      });
    }
  };

  const handleCreate = async (data: EvaluationWizardData) => {
    const created = await createTestEvaluation({
      name: data.name.trim(),
      description: data.description.trim() || undefined,
      suite_id: data.suiteId,
      workflow_id: data.workflowId === "none" ? undefined : data.workflowId,
      techniques: data.metrics,
      technique_configs: buildTechniqueConfigs(data),
      input_metadata: wizardMetadata(data),
    });
    if (!created) return;
    setIsCreateDialogOpen(false);
    navigate(`/tests/evaluations/${created.id}`);
  };

  const renderRow = (row: WorkflowRow) => {
    const isPending = row.workflowId ? runningWorkflowIds.has(row.workflowId) : false;
    const isRunning = isPending || row.anyRunning;
    const healthTooltip = row.anyRunning
      ? row.health !== null
        ? "Evaluations running; health shown is from the previous completed runs."
        : "Evaluations are running…"
      : row.health !== null
        ? `Health from ${row.finishedCount} of ${row.count} evaluation${
            row.count !== 1 ? "s" : ""
          } (failed runs count as 0%)`
        : "No evaluations scored yet";
    return (
      <tr
        key={row.key}
        onClick={() => openWorkflow(row)}
        className="hover:bg-gray-50 transition-colors cursor-pointer"
      >
        <td className="px-6 py-4">
          <div className="flex items-center gap-2 min-w-0">
            <Layers className="h-4 w-4 text-gray-400 shrink-0" />
            <EntityTitle muted={row.isUnassigned}>{row.name}</EntityTitle>
          </div>
        </td>
        <td className="px-6 py-4">
          <div className="flex items-center gap-1.5" title={healthTooltip}>
            {row.anyRunning ? (
              <Loader2 className="h-3.5 w-3.5 text-blue-600 animate-spin" />
            ) : (
              <Activity className="h-3.5 w-3.5 text-gray-400" />
            )}
            {row.health !== null ? (
              <span className={cn("font-medium", accuracyColorClass(row.health))}>
                {Math.round(row.health * 100)}%
              </span>
            ) : row.anyRunning ? (
              <span className="text-blue-600">Running…</span>
            ) : (
              <span className="text-gray-400">No scores yet</span>
            )}
          </div>
        </td>
        <td className="px-6 py-4">
          <Badge variant="secondary">
            {row.count} eval{row.count !== 1 ? "s" : ""}
          </Badge>
        </td>
        <td className="px-6 py-4" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-end gap-2">
            {!row.isUnassigned && row.count > 0 && row.workflowId && (
              <Button
                variant="outline"
                size="sm"
                disabled={isRunning}
                onClick={() => handleRunAll(row.workflowId as string)}
              >
                <Play className="h-3.5 w-3.5 mr-1" />
                {isRunning ? "Running..." : "Run all"}
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={() => openWorkflow(row)}>
              Open
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </td>
      </tr>
    );
  };

  return (
    <PageLayout>
      <PageHeader
        title="Evaluations"
        subtitle="Grouped by workflow. Open a workflow to view and run its evaluations."
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search workflows..."
        actionButtonText="New Evaluation"
        onActionClick={() => setIsCreateDialogOpen(true)}
      />

      <div className="rounded-lg border bg-white overflow-hidden">
        {isLoading ? (
          <PageListSkeleton variant="evaluation" bordered={false} />
        ) : hasError ? (
          <div className="py-16 text-center">
            <p className="text-sm text-gray-500 mb-3">Couldn't load evaluations.</p>
            <Button
              variant="outline"
              onClick={() => {
                setReloadKey((key) => key + 1);
                void refetchSummaries();
              }}
            >
              Retry
            </Button>
          </div>
        ) : rows.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
            <div className="rounded-full bg-gray-100 p-4">
              <ListChecks className="h-12 w-12 text-gray-400" />
            </div>
            <h3 className="font-medium text-lg">No evaluations yet</h3>
            <p className="text-sm text-gray-500 max-w-sm">
              {searchQuery
                ? "No workflows match your search."
                : "Evaluations help you test your AI agents against golden datasets. Create your first evaluation to get started."}
            </p>
            {!searchQuery && (
              <Button onClick={() => setIsCreateDialogOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Create your first evaluation
              </Button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                  <th className="px-6 py-3 font-medium">Workflow</th>
                  <th className="px-6 py-3 font-medium">Health</th>
                  <th className="px-6 py-3 font-medium">Evaluations</th>
                  <th className="px-6 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">{rows.map(renderRow)}</tbody>
            </table>
          </div>
        )}
      </div>

      <EvaluationWizard
        isOpen={isCreateDialogOpen}
        onOpenChange={setIsCreateDialogOpen}
        onSubmit={handleCreate}
        suites={suites}
        workflows={workflows}
        providers={providers}
        mode="create"
      />
    </PageLayout>
  );
};

export default EvaluationsPage;
