import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Activity, ListChecks, Loader2, Plus, Upload } from "lucide-react";

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
} from "@/services/testEvaluations";
import { WorkflowMinimal } from "@/interfaces/workflow.interface";
import { TestSuite } from "@/interfaces/testSuite.interface";
import { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";
import { EvaluationWizard, EvaluationWizardData } from "../components/EvaluationWizard";
import { ImportEvaluationDialog } from "../components/ImportEvaluationDialog";
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

// Rows are named after the agent, matching Agent Studio and the workflow picker.
// Two versions of one agent would then read identically, so those keep a version.
const nameRows = (rows: WorkflowRow[], workflows: WorkflowMinimal[]): WorkflowRow[] => {
  const counts = new Map<string, number>();
  rows.forEach((row) => counts.set(row.name, (counts.get(row.name) ?? 0) + 1));

  return rows.map((row) => {
    if ((counts.get(row.name) ?? 0) < 2) return row;
    const version = workflows.find((w) => w.id === row.workflowId)?.version;
    return version ? { ...row, name: `${row.name} · v${version}` } : row;
  });
};

const EvaluationsPage: React.FC = () => {
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState<WorkflowMinimal[]>([]);
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [providers, setProviders] = useState<LLMProviderMinimal[]>([]);
  const [isReferenceLoading, setIsReferenceLoading] = useState(true);
  const [hasReferenceError, setHasReferenceError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isImportDialogOpen, setIsImportDialogOpen] = useState(false);

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
      const workflow = workflows.find((w) => w.id === workflowId);
      if (!workflow) return "Unknown workflow";
      return workflow.agent_name || workflow.name;
    };
    const query = searchQuery.trim().toLowerCase();
    const named = nameRows(
      summaries.map((summary) => ({
        key: summary.workflow_id ?? UNASSIGNED,
        workflowId: summary.workflow_id,
        name: nameFor(summary.workflow_id),
        count: summary.eval_count,
        health: summary.health,
        finishedCount: summary.finished_count,
        anyRunning: summary.any_running,
        isUnassigned: summary.workflow_id === null,
      })),
      workflows,
    );
    return named
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
    const healthTooltip = row.anyRunning
      ? row.health !== null
        ? "Evaluations running; accuracy shown is from the previous completed runs."
        : "Evaluations are running…"
      : row.health !== null
        ? `Accuracy from ${row.finishedCount} of ${row.count} evaluation${
            row.count !== 1 ? "s" : ""
          } (failed runs count as 0%)`
        : "No evaluations scored yet";
    return (
      <tr
        key={row.key}
        onClick={() => openWorkflow(row)}
        className="hover:bg-muted transition-colors cursor-pointer"
      >
        <td className="px-6 py-4">
          <div className="flex items-center gap-2 min-w-0">
            <EntityTitle muted={row.isUnassigned}>{row.name}</EntityTitle>
          </div>
        </td>
        <td className="px-6 py-4">
          <div className="flex items-center gap-1.5" title={healthTooltip}>
            {row.anyRunning ? (
              <Loader2 className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400 animate-spin" />
            ) : (
              <Activity className="h-3.5 w-3.5 text-muted-foreground" />
            )}
            {row.health !== null ? (
              <span className={cn("font-medium", accuracyColorClass(row.health))}>
                {Math.round(row.health * 100)}%
              </span>
            ) : row.anyRunning ? (
              <span className="text-blue-600 dark:text-blue-400">Running…</span>
            ) : (
              <span className="text-muted-foreground">No scores yet</span>
            )}
          </div>
        </td>
        <td className="px-6 py-4">
          <Badge variant="secondary">
            {row.count} eval{row.count !== 1 ? "s" : ""}
          </Badge>
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
        secondaryActionButtonText={
          <>
            <Upload className="w-4 h-4" />
            Import
          </>
        }
        onSecondaryActionClick={() => setIsImportDialogOpen(true)}
      />

      <div className="rounded-lg border bg-card dark:bg-zinc-900 overflow-hidden">
        {isLoading ? (
          <PageListSkeleton variant="evaluation" bordered={false} />
        ) : hasError ? (
          <div className="py-16 text-center">
            <p className="text-sm text-muted-foreground mb-3">Couldn't load evaluations.</p>
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
            <div className="rounded-full bg-muted p-4">
              <ListChecks className="h-12 w-12 text-muted-foreground" />
            </div>
            <h3 className="font-medium text-lg">No evaluations yet</h3>
            <p className="text-sm text-muted-foreground max-w-sm">
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
                <tr className="border-b bg-muted text-left text-xs font-medium text-muted-foreground">
                  <th className="px-6 py-3 font-medium">Workflow</th>
                  <th className="px-6 py-3 font-medium">Accuracy</th>
                  <th className="px-6 py-3 font-medium">Evaluations</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">{rows.map(renderRow)}</tbody>
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

      <ImportEvaluationDialog
        isOpen={isImportDialogOpen}
        onOpenChange={setIsImportDialogOpen}
        workflows={workflows}
        onImported={(result) => {
          void refetchSummaries();
          navigate(`/tests/evaluations/${result.evaluation_id}`);
        }}
        onSetImported={() => void refetchSummaries()}
      />
    </PageLayout>
  );
};

export default EvaluationsPage;
