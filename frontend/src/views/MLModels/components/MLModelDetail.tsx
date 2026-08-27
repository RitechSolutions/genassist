import React, { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-hot-toast";
import {
  AlertCircle,
  Calendar,
  ChevronLeft,
  Clock,
  Download,
  ExternalLink,
  FileCode,
  Loader2,
  Pencil,
  Play,
  Plus,
  RefreshCcw,
  Star,
  Trash2,
  Workflow as WorkflowIcon,
} from "lucide-react";

import { PageLayout } from "@/components/PageLayout";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { RadioGroup, RadioGroupItem } from "@/components/radio-group";
import { SearchInput } from "@/components/SearchInput";
import { Skeleton } from "@/components/skeleton";
import { ListEmptyState } from "@/components/ListEmptyState";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import JsonViewer, { JsonValue } from "@/components/JsonViewer";
import { FormField } from "@/components/ui/form-field";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/resizable";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { cn } from "@/lib/utils";

import { getMLModel } from "@/services/mlModels";
import {
  createPipelineConfig,
  createPipelineRun,
  deletePipelineConfig,
  downloadPipelineArtifact,
  getModelPipelineConfigs,
  getModelPipelineRuns,
  getPipelineRunArtifacts,
  promotePipelineRun,
  updatePipelineConfig,
} from "@/services/mlModelPipelines";
import { createWorkflow, getAllWorkflows } from "@/services/workflows";
import { MLModel } from "@/interfaces/ml-model.interface";
import {
  PipelineArtifact,
  PipelineRun,
  TrainingPipelineConfig,
} from "@/interfaces/ml-model-pipeline.interface";
import { Workflow, WorkflowCreatePayload } from "@/interfaces/workflow.interface";
import { formatDateTime } from "@/helpers/utils";
import { downloadFileManagerFile } from "@/services/fileManager";
import { modelTypeLabel } from "../helpers/modelTypes";
import {
  CRON_PRESETS,
  CUSTOM_CRON,
  describeCron,
  formatFileSize,
  formatRunDuration,
  hasActiveRun,
  isRunActive,
  isRunDefaultPipeline,
  isRunFullyPromoted,
  isRunPromoted,
  isValidCron,
  runModelFilePath,
  runStatusMeta,
} from "../helpers/pipelineRuns";

/** While a run is pending or running, refresh the list so it settles on its own. */
const RUNNING_POLL_MS = 5000;

/** Small uppercase caption + value, matching the Evaluations detail summary cards. */
const Field: React.FC<{ label: string; children: React.ReactNode; className?: string }> = ({
  label,
  children,
  className,
}) => (
  <div className={cn("min-w-0", className)}>
    <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
      {label}
    </div>
    <div className="mt-0.5 text-sm font-medium">{children}</div>
  </div>
);

const SectionCard: React.FC<{
  title: string;
  action?: React.ReactNode;
  meta?: React.ReactNode;
  children: React.ReactNode;
}> = ({ title, action, meta, children }) => (
  <section className="rounded-lg border bg-card p-4 sm:p-6 dark:bg-zinc-900">
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold">{title}</h2>
        {meta}
      </div>
      {action}
    </div>
    {children}
  </section>
);

const RunStatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const meta = runStatusMeta(status);
  return (
    <Badge variant="outline" className={cn("gap-1 font-medium", meta.className)}>
      {meta.spinning && <Loader2 className="h-3 w-3 animate-spin" />}
      {meta.label}
    </Badge>
  );
};

/**
 * A run is "promoted" when the model points at the file that run produced — the
 * backend stores no flag on the run itself, so the state is derived.
 */
const PromotedBadge: React.FC = () => (
  <Badge
    variant="outline"
    className="gap-1 border-transparent bg-amber-100 font-medium text-amber-800 dark:bg-amber-500/20 dark:text-amber-400"
    title="This run's output is the model's active file"
  >
    <Star className="h-3 w-3 fill-current" />
    Promoted
  </Badge>
);

/** The run used the pipeline configuration that is currently the model's default. */
const DefaultPipelineBadge: React.FC = () => (
  <Badge
    variant="outline"
    className="gap-1 font-normal"
    title="This run's pipeline is the model's default"
  >
    Default pipeline
  </Badge>
);

const DetailSkeleton: React.FC = () => (
  <PageLayout>
    <div className="flex items-center gap-3">
      <Skeleton className="h-10 w-10 rounded-md" />
      <div className="space-y-2">
        <Skeleton className="h-7 w-56" />
        <Skeleton className="h-4 w-72" />
      </div>
    </div>
    {[0, 1, 2].map((i) => (
      <div key={i} className="space-y-3 rounded-lg border bg-card p-6 dark:bg-zinc-900">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    ))}
  </PageLayout>
);

const MLModelDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [showConfigDialog, setShowConfigDialog] = useState(false);
  const [showCreateWorkflowDialog, setShowCreateWorkflowDialog] = useState(false);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState("");
  const [workflowSearch, setWorkflowSearch] = useState("");
  // The schedule picker holds either a preset cron string, "" for manual, or
  // CUSTOM_CRON; `cronSchedule` is only the free-text value behind "custom".
  const [cronMode, setCronMode] = useState<string>("");
  const [cronSchedule, setCronSchedule] = useState("");
  const [cronError, setCronError] = useState<string | null>(null);
  const [makeDefault, setMakeDefault] = useState(true);
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [newWorkflowName, setNewWorkflowName] = useState("");
  const [newWorkflowDescription, setNewWorkflowDescription] = useState("");
  const [isCreatingWorkflow, setIsCreatingWorkflow] = useState(false);

  // Per-item busy flags: the previous single flag made every row's button
  // spin whenever any one of them was working.
  const [runningConfigId, setRunningConfigId] = useState<string | null>(null);
  const [defaultingConfigId, setDefaultingConfigId] = useState<string | null>(null);
  const [promotingRunId, setPromotingRunId] = useState<string | null>(null);
  const [downloadingArtifactId, setDownloadingArtifactId] = useState<string | null>(null);
  const [isDownloadingModel, setIsDownloadingModel] = useState(false);
  const [isRefreshingRuns, setIsRefreshingRuns] = useState(false);

  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null);
  const [configToDelete, setConfigToDelete] = useState<TrainingPipelineConfig | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const modelQuery = useQuery({
    queryKey: ["ml-model", id],
    queryFn: () => getMLModel(id as string),
    enabled: !!id,
  });

  const configsQuery = useQuery({
    queryKey: ["ml-model-pipeline-configs", id],
    queryFn: () => getModelPipelineConfigs(id as string),
    enabled: !!id,
  });

  // Runs poll only while something is in flight; react-query pauses the interval
  // in a hidden tab, so a finished run appears without a manual refresh.
  const runsQuery = useQuery({
    queryKey: ["ml-model-pipeline-runs", id],
    queryFn: () => getModelPipelineRuns(id as string),
    enabled: !!id,
    // Run state moves on its own, so never serve it from a stale cache on return.
    staleTime: 0,
    refetchInterval: (query) =>
      hasActiveRun(query.state.data ?? []) ? RUNNING_POLL_MS : false,
  });

  const workflowsQuery = useQuery({
    queryKey: ["workflows-all"],
    queryFn: getAllWorkflows,
  });

  const artifactsQuery = useQuery({
    queryKey: ["ml-model-pipeline-artifacts", id, selectedRun?.id],
    queryFn: () => getPipelineRunArtifacts(id as string, selectedRun?.id as string),
    enabled: !!id && !!selectedRun?.id,
  });

  const model: MLModel | null = modelQuery.data ?? null;
  const configs = configsQuery.data ?? [];
  const workflows: Workflow[] = workflowsQuery.data ?? [];
  const artifacts: PipelineArtifact[] = artifactsQuery.data ?? [];

  const runs = useMemo(
    () =>
      [...(runsQuery.data ?? [])].sort(
        (a, b) =>
          new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime()
      ),
    [runsQuery.data]
  );

  const workflowById = useMemo(
    () => new Map((workflowsQuery.data ?? []).map((workflow) => [workflow.id, workflow])),
    [workflowsQuery.data]
  );
  const workflowName = (workflowId: string) =>
    workflowById.get(workflowId)?.name ?? "Unknown workflow";

  const activeRunCount = runs.filter((run) => isRunActive(run.status)).length;
  const defaultConfigId = configs.find((config) => config.is_default)?.id ?? null;

  // The first configuration is always the default, so the toggle is forced on.
  const isFirstConfig = configs.length === 0;
  const configuredWorkflowIds = useMemo(
    () => new Set((configsQuery.data ?? []).map((config) => config.workflow_id)),
    [configsQuery.data]
  );

  const filteredWorkflows = useMemo(() => {
    const query = workflowSearch.trim().toLowerCase();
    return (workflowsQuery.data ?? [])
      .filter(
        (workflow) =>
          !query ||
          workflow.name?.toLowerCase().includes(query) ||
          workflow.description?.toLowerCase().includes(query)
      )
      .sort((a, b) => (a.name ?? "").localeCompare(b.name ?? ""));
  }, [workflowsQuery.data, workflowSearch]);

  /** The cron string the picker currently resolves to ("" = manual only). */
  const effectiveCron = cronMode === CUSTOM_CRON ? cronSchedule.trim() : cronMode;

  const scheduleSummary = useMemo(() => {
    if (!effectiveCron) return "Runs only when you click Run now.";
    const described = describeCron(effectiveCron);
    if (described) return `Runs automatically: ${described.toLowerCase()}.`;
    return isValidCron(effectiveCron)
      ? `Runs automatically on the schedule "${effectiveCron}".`
      : "Enter five cron fields, e.g. 0 3 * * 1-5.";
  }, [effectiveCron]);

  const invalidateRuns = () =>
    queryClient.invalidateQueries({ queryKey: ["ml-model-pipeline-runs", id] });
  const invalidateConfigs = () =>
    queryClient.invalidateQueries({ queryKey: ["ml-model-pipeline-configs", id] });

  const resetConfigDialog = () => {
    setSelectedWorkflowId("");
    setWorkflowSearch("");
    setCronMode("");
    setCronSchedule("");
    setCronError(null);
  };

  const openConfigDialog = () => {
    resetConfigDialog();
    setMakeDefault(configs.length === 0);
    setShowConfigDialog(true);
  };

  const handleCronModeChange = (mode: string) => {
    setCronMode(mode);
    setCronError(null);
  };

  const handleCreateConfig = async () => {
    if (!id) return;
    if (!selectedWorkflowId) {
      toast.error("Select a workflow first.");
      return;
    }
    if (!isValidCron(effectiveCron)) {
      setCronMode(CUSTOM_CRON);
      setCronError("Expected 5 fields, e.g. 0 0 * * * for daily at midnight.");
      return;
    }
    try {
      setIsSavingConfig(true);
      await createPipelineConfig(id, {
        model_id: id,
        workflow_id: selectedWorkflowId,
        cron_schedule: effectiveCron || null,
        is_default: isFirstConfig || makeDefault,
      });
      toast.success("Pipeline configuration created.");
      setShowConfigDialog(false);
      resetConfigDialog();
      await invalidateConfigs();
    } catch {
      toast.error("Failed to create pipeline configuration.");
    } finally {
      setIsSavingConfig(false);
    }
  };

  const handleCreateWorkflow = async () => {
    if (!newWorkflowName.trim()) {
      toast.error("Enter a workflow name.");
      return;
    }
    try {
      setIsCreatingWorkflow(true);
      // The workflow is created empty on purpose — its nodes/edges and agent are
      // set up afterwards in the Workflow Studio, so only the identity fields are
      // sent (the payload type also covers full builder saves).
      const payload = {
        name: newWorkflowName.trim(),
        description: newWorkflowDescription.trim(),
        version: "1.0.0",
      } as WorkflowCreatePayload;
      const created = await createWorkflow(payload);
      toast.success("Workflow created. Configure its steps in the Workflow Studio.");
      setShowCreateWorkflowDialog(false);
      setNewWorkflowName("");
      setNewWorkflowDescription("");
      await queryClient.invalidateQueries({ queryKey: ["workflows-all"] });
      setSelectedWorkflowId(created?.id ?? "");
      setShowConfigDialog(true);
    } catch {
      toast.error("Failed to create workflow.");
    } finally {
      setIsCreatingWorkflow(false);
    }
  };

  const handleRunPipeline = async (config: TrainingPipelineConfig) => {
    if (!id) return;
    try {
      setRunningConfigId(config.id);
      await createPipelineRun(id, {
        model_id: id,
        pipeline_config_id: config.id,
        workflow_id: config.workflow_id,
      });
      toast.success("Pipeline run started.");
      await invalidateRuns();
    } catch {
      toast.error("Failed to start pipeline run.");
    } finally {
      setRunningConfigId(null);
    }
  };

  const handleSetDefault = async (config: TrainingPipelineConfig) => {
    if (!id) return;
    try {
      setDefaultingConfigId(config.id);
      await updatePipelineConfig(id, config.id, { is_default: true });
      await Promise.all(
        configs
          .filter((other) => other.id !== config.id && other.is_default)
          .map((other) => updatePipelineConfig(id, other.id, { is_default: false }))
      );
      toast.success("Default configuration updated.");
      await invalidateConfigs();
    } catch {
      toast.error("Failed to update the default configuration.");
    } finally {
      setDefaultingConfigId(null);
    }
  };

  const handlePromoteRun = async (run: PipelineRun) => {
    if (!id) return;
    try {
      setPromotingRunId(run.id);
      const result = await promotePipelineRun(id, run.id);
      toast.success(
        result?.model_updated
          ? "Run promoted. The model now uses this run's file, target and features."
          : "Run promoted. Its pipeline is now the default (the run produced no model file)."
      );
      await Promise.all([
        invalidateConfigs(),
        invalidateRuns(),
        queryClient.invalidateQueries({ queryKey: ["ml-model", id] }),
        queryClient.invalidateQueries({ queryKey: ["ml-models"] }),
      ]);
    } catch {
      toast.error("Failed to promote the pipeline run.");
    } finally {
      setPromotingRunId(null);
    }
  };

  const handleDeleteConfig = async () => {
    if (!id || !configToDelete) return;
    try {
      setIsDeleting(true);
      await deletePipelineConfig(id, configToDelete.id);
      toast.success("Pipeline configuration deleted.");
      await invalidateConfigs();
    } catch {
      toast.error("Failed to delete the pipeline configuration.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setConfigToDelete(null);
    }
  };

  const handleDownloadModelFile = async () => {
    if (!model?.pkl_file_id) return;
    try {
      setIsDownloadingModel(true);
      await downloadFileManagerFile(model.pkl_file_id, `${model.name || "model"}.pkl`);
    } catch {
      toast.error("Failed to download the model file.");
    } finally {
      setIsDownloadingModel(false);
    }
  };

  // Explicit refresh, tracked separately from `isFetching` so the background
  // poll doesn't put the button into a loading state every few seconds.
  const handleRefreshRuns = async () => {
    try {
      setIsRefreshingRuns(true);
      await runsQuery.refetch();
    } finally {
      setIsRefreshingRuns(false);
    }
  };

  const handleDownloadArtifact = async (artifact: PipelineArtifact) => {
    if (!id || !selectedRun?.id) return;
    try {
      setDownloadingArtifactId(artifact.id);
      await downloadPipelineArtifact(id, selectedRun.id, artifact.id, artifact.artifact_name);
    } catch {
      toast.error("Failed to download the artifact.");
    } finally {
      setDownloadingArtifactId(null);
    }
  };

  if (modelQuery.isPending) return <DetailSkeleton />;

  if (modelQuery.isError || !model) {
    return (
      <PageLayout>
        <ListEmptyState
          icon={<AlertCircle className="h-12 w-12 text-muted-foreground" />}
          title="Model not found"
          description="This ML model may have been deleted, or the link is no longer valid."
          action={
            <Button onClick={() => navigate("/ml-models")} className="rounded-full">
              Back to ML Models
            </Button>
          }
        />
      </PageLayout>
    );
  }

  return (
    <PageLayout>
      {/* Header: back + identity + primary actions */}
      <div className="flex flex-wrap items-start gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate("/ml-models")}
          aria-label="Back to ML Models"
          className="shrink-0"
        >
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="truncate text-2xl font-bold tracking-tight animate-fade-down md:text-3xl">
              {model.name}
            </h1>
            <Badge variant="secondary">{modelTypeLabel(model.model_type)}</Badge>
          </div>
          {model.description && (
            <p className="mt-1 text-sm text-muted-foreground animate-fade-up">
              {model.description}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {model.pkl_file_id && (
            <Button
              variant="outline"
              className="rounded-full"
              loading={isDownloadingModel}
              icon={<Download className="h-4 w-4" />}
              onClick={handleDownloadModelFile}
            >
              Model file
            </Button>
          )}
          <Button
            variant="outline"
            className="rounded-full"
            icon={<Pencil className="h-4 w-4" />}
            onClick={() => navigate("/ml-models", { state: { editModelId: model.id } })}
          >
            Edit
          </Button>
        </div>
      </div>

      {/* Overview */}
      <SectionCard title="Model information">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Field label="Model type">{modelTypeLabel(model.model_type)}</Field>
          <Field label="Target variable">
            <span className="font-mono text-xs">{model.target_variable || "—"}</span>
          </Field>
          <Field label="Created">
            <span className="text-muted-foreground">{formatDateTime(model.created_at)}</span>
          </Field>
          <Field label="Last updated">
            <span className="text-muted-foreground">{formatDateTime(model.updated_at)}</span>
          </Field>
        </div>

        <div className="mt-5 border-t pt-4">
          <Field label={`Features (${model.features?.length ?? 0})`}>
            {model.features?.length ? (
              <div className="mt-1 flex flex-wrap gap-1">
                {model.features.map((feature) => (
                  <Badge key={feature} variant="secondary" className="font-normal">
                    {feature}
                  </Badge>
                ))}
              </div>
            ) : (
              <span className="text-muted-foreground">No features defined.</span>
            )}
          </Field>
        </div>
      </SectionCard>

      {/* Training pipeline configurations */}
      <SectionCard
        title="Training pipelines"
        meta={
          configs.length > 0 ? (
            <Badge variant="secondary">
              {configs.length} config{configs.length !== 1 ? "s" : ""}
            </Badge>
          ) : null
        }
        action={
          configs.length > 0 ? (
            <Button
              variant="outline"
              className="rounded-full"
              icon={<Plus className="h-4 w-4" />}
              onClick={openConfigDialog}
            >
              Add configuration
            </Button>
          ) : null
        }
      >
        {configsQuery.isPending ? (
          <div className="space-y-2">
            <Skeleton className="h-20 w-full rounded-lg" />
            <Skeleton className="h-20 w-full rounded-lg" />
          </div>
        ) : configs.length === 0 ? (
          <ListEmptyState
            icon={<WorkflowIcon className="h-10 w-10 text-muted-foreground" />}
            title="No pipeline configuration"
            description="Point this model at a training workflow to start producing runs, on demand or on a schedule."
            action={
              <Button className="rounded-full" onClick={openConfigDialog}>
                <Plus className="mr-2 h-4 w-4" />
                Configure pipeline
              </Button>
            }
          />
        ) : (
          <div className="space-y-3">
            {configs.map((config) => {
              const workflow = workflowById.get(config.workflow_id);
              return (
                <div
                  key={config.id}
                  className="flex flex-col gap-3 rounded-lg border p-4 transition-colors hover:bg-muted/50 sm:flex-row sm:items-start sm:justify-between"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="truncate font-medium">
                        {workflow?.name ?? "Unknown workflow"}
                      </h3>
                      {config.is_default && (
                        <Badge className="gap-1">
                          <Star className="h-3 w-3" />
                          Default
                        </Badge>
                      )}
                      {config.cron_schedule ? (
                        <Badge variant="outline" className="gap-1 font-mono text-xs">
                          <Calendar className="h-3 w-3" />
                          {config.cron_schedule}
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="font-normal">
                          Manual only
                        </Badge>
                      )}
                    </div>
                    {workflow?.description && (
                      <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                        {workflow.description}
                      </p>
                    )}
                    {workflow?.version && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Version {workflow.version}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-2">
                    {!config.is_default && (
                      <Button
                        variant="outline"
                        size="sm"
                        loading={defaultingConfigId === config.id}
                        icon={<Star className="h-4 w-4" />}
                        onClick={() => handleSetDefault(config)}
                      >
                        Set default
                      </Button>
                    )}
                    <Button
                      size="sm"
                      loading={runningConfigId === config.id}
                      icon={<Play className="h-4 w-4" />}
                      onClick={() => handleRunPipeline(config)}
                    >
                      Run now
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-9 w-9 text-red-500"
                      aria-label="Delete configuration"
                      onClick={() => {
                        setConfigToDelete(config);
                        setIsDeleteDialogOpen(true);
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </SectionCard>

      {/* Run history */}
      <SectionCard
        title="Execution history"
        meta={
          <>
            {runs.length > 0 && (
              <Badge variant="secondary">
                {runs.length} run{runs.length !== 1 ? "s" : ""}
              </Badge>
            )}
            {activeRunCount > 0 && (
              <Badge variant="outline" className="gap-1 text-blue-600 dark:text-blue-400">
                <Loader2 className="h-3 w-3 animate-spin" />
                {activeRunCount} active
              </Badge>
            )}
          </>
        }
        action={
          <Button
            variant="outline"
            size="sm"
            className="rounded-full"
            loading={isRefreshingRuns}
            icon={<RefreshCcw className="h-4 w-4" />}
            onClick={() => void handleRefreshRuns()}
          >
            Refresh
          </Button>
        }
      >
        {runsQuery.isPending ? (
          <div className="space-y-2">
            <Skeleton className="h-16 w-full rounded-lg" />
            <Skeleton className="h-16 w-full rounded-lg" />
            <Skeleton className="h-16 w-full rounded-lg" />
          </div>
        ) : runs.length === 0 ? (
          <ListEmptyState
            icon={<Clock className="h-10 w-10 text-muted-foreground" />}
            title="No pipeline runs"
            description="Execution history appears here once a training pipeline has run."
          />
        ) : (
          <div className="space-y-2">
            {runs.map((run) => {
              const duration = formatRunDuration(run.started_at, run.completed_at);
              const isSuccessful = run.status === "completed";
              const isPromoted = isRunPromoted(run, model.pkl_file);
              const isDefaultPipeline = isRunDefaultPipeline(run, defaultConfigId);
              const isFullyPromoted = isRunFullyPromoted(
                run,
                model.pkl_file,
                defaultConfigId
              );
              return (
                <div
                  key={run.id}
                  tabIndex={0}
                  onClick={() => setSelectedRun(run)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelectedRun(run);
                    }
                  }}
                  className="w-full cursor-pointer rounded-lg border p-3 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">Run #{run.id?.slice(-6)}</span>
                        <RunStatusBadge status={run.status} />
                        {isPromoted && <PromotedBadge />}
                        {isDefaultPipeline && <DefaultPipelineBadge />}
                        <span className="truncate text-sm text-muted-foreground">
                          {workflowName(run.workflow_id)}
                        </span>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                        <span>{formatDateTime(run.started_at ?? run.created_at)}</span>
                        {duration && <span>Duration {duration}</span>}
                      </div>
                      {run.error_message && (
                        <p className="mt-2 line-clamp-2 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700 dark:border-red-500/30 dark:bg-red-500/15 dark:text-red-400">
                          {run.error_message}
                        </p>
                      )}
                    </div>
                    <div
                      className="flex shrink-0 items-center gap-2"
                      onClick={(e) => e.stopPropagation()}
                      onKeyDown={(e) => e.stopPropagation()}
                    >
                      {isSuccessful &&
                        (isFullyPromoted ? (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled
                            // disabled:opacity-100 keeps the green readable —
                            // the base button dims disabled states to 50%.
                            className="border-green-600/40 bg-green-50 text-green-700 disabled:opacity-100 dark:border-green-500/30 dark:bg-green-500/15 dark:text-green-400"
                            icon={<Star className="h-4 w-4 fill-current" />}
                            title="This run is already the model's active pipeline"
                          >
                            Promoted
                          </Button>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            loading={promotingRunId === run.id}
                            icon={<Star className="h-4 w-4" />}
                            onClick={() => handlePromoteRun(run)}
                          >
                            Promote
                          </Button>
                        ))}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </SectionCard>

      {/* Create configuration */}
      <Dialog
        open={showConfigDialog}
        onOpenChange={(open) => {
          setShowConfigDialog(open);
          if (!open) resetConfigDialog();
        }}
      >
        <DialogContent className="flex max-h-[88vh] w-[95vw] max-w-6xl flex-col">
          <DialogHeader>
            <DialogTitle>Configure training pipeline</DialogTitle>
            <DialogDescription>
              Choose the workflow that trains <span className="font-medium">{model.name}</span>,
              and how often it should run.
            </DialogDescription>
          </DialogHeader>

          <div className="grid min-h-0 flex-1 gap-6 py-1 md:grid-cols-5">
            {/* Workflow picker */}
            <div className="flex min-h-0 flex-col gap-3 md:col-span-3">
              <div className="flex items-center justify-between gap-2">
                <Label className="text-sm font-medium">Training workflow</Label>
                <Button
                  variant="link"
                  size="sm"
                  className="h-auto p-0"
                  onClick={() => {
                    setShowConfigDialog(false);
                    setShowCreateWorkflowDialog(true);
                  }}
                >
                  <Plus className="mr-1 h-4 w-4" />
                  New workflow
                </Button>
              </div>

              <SearchInput
                value={workflowSearch}
                onChange={setWorkflowSearch}
                placeholder="Search workflows..."
              />

              <div className="min-h-[16rem] flex-1 overflow-y-auto rounded-lg border p-1 md:h-[22rem]">
                {workflowsQuery.isPending ? (
                  <div className="space-y-1 p-2">
                    {[0, 1, 2, 3].map((i) => (
                      <Skeleton key={i} className="h-14 w-full rounded-md" />
                    ))}
                  </div>
                ) : filteredWorkflows.length === 0 ? (
                  <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
                    <WorkflowIcon className="h-8 w-8 text-muted-foreground" />
                    <p className="text-sm font-medium">
                      {workflowSearch ? "No matching workflows" : "No workflows yet"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {workflowSearch
                        ? "Try a different search term."
                        : "Create a workflow first, then point this model at it."}
                    </p>
                  </div>
                ) : (
                  <RadioGroup
                    value={selectedWorkflowId}
                    onValueChange={setSelectedWorkflowId}
                    className="gap-1"
                  >
                    {filteredWorkflows.map((workflow) => {
                      const workflowId = workflow.id || "";
                      const isSelected = selectedWorkflowId === workflowId;
                      const isConfigured = configuredWorkflowIds.has(workflowId);
                      return (
                        <div
                          key={workflowId}
                          onClick={() => setSelectedWorkflowId(workflowId)}
                          className={cn(
                            "flex cursor-pointer items-start gap-3 rounded-md border p-3 transition-colors",
                            isSelected
                              ? "border-primary bg-primary/5"
                              : "border-transparent hover:bg-muted"
                          )}
                        >
                          <RadioGroupItem
                            value={workflowId}
                            id={`workflow-${workflowId}`}
                            className="mt-0.5 shrink-0"
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <Label
                                htmlFor={`workflow-${workflowId}`}
                                className="cursor-pointer truncate text-sm font-medium"
                              >
                                {workflow.name}
                              </Label>
                              {workflow.version && (
                                <Badge variant="outline" className="text-[10px]">
                                  v{workflow.version}
                                </Badge>
                              )}
                              {isConfigured && (
                                <Badge variant="secondary" className="text-[10px] font-normal">
                                  Already configured
                                </Badge>
                              )}
                            </div>
                            {workflow.description && (
                              <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                                {workflow.description}
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </RadioGroup>
                )}
              </div>

              <Button
                variant="link"
                size="sm"
                className="h-auto justify-start p-0 text-muted-foreground"
                onClick={() => window.open("/ai-agents", "_blank")}
              >
                <ExternalLink className="mr-1 h-4 w-4" />
                Open Workflow Studio
              </Button>
            </div>

            {/* Schedule */}
            <div className="flex min-h-0 flex-col gap-3 md:col-span-2">
              <Label className="text-sm font-medium">Schedule</Label>

              <RadioGroup value={cronMode} onValueChange={handleCronModeChange} className="gap-1">
                {CRON_PRESETS.map((preset) => (
                  <div
                    key={preset.value || "manual"}
                    onClick={() => handleCronModeChange(preset.value)}
                    className={cn(
                      "flex cursor-pointer items-start gap-3 rounded-md border p-2.5 transition-colors",
                      cronMode === preset.value
                        ? "border-primary bg-primary/5"
                        : "border-transparent hover:bg-muted"
                    )}
                  >
                    <RadioGroupItem
                      value={preset.value}
                      id={`cron-${preset.value || "manual"}`}
                      className="mt-0.5 shrink-0"
                    />
                    <div className="min-w-0">
                      <Label
                        htmlFor={`cron-${preset.value || "manual"}`}
                        className="cursor-pointer text-sm font-medium"
                      >
                        {preset.label}
                      </Label>
                      <p className="text-xs text-muted-foreground">{preset.hint}</p>
                    </div>
                  </div>
                ))}

                <div
                  onClick={() => handleCronModeChange(CUSTOM_CRON)}
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-md border p-2.5 transition-colors",
                    cronMode === CUSTOM_CRON
                      ? "border-primary bg-primary/5"
                      : "border-transparent hover:bg-muted"
                  )}
                >
                  <RadioGroupItem
                    value={CUSTOM_CRON}
                    id="cron-custom"
                    className="mt-0.5 shrink-0"
                  />
                  <div className="min-w-0 flex-1">
                    <Label htmlFor="cron-custom" className="cursor-pointer text-sm font-medium">
                      Custom cron
                    </Label>
                    {cronMode === CUSTOM_CRON ? (
                      <>
                        <Input
                          className="mt-1.5 font-mono"
                          placeholder="0 3 * * 1-5"
                          value={cronSchedule}
                          autoFocus
                          onChange={(e) => {
                            setCronSchedule(e.target.value);
                            if (cronError) setCronError(null);
                          }}
                        />
                        {cronError && (
                          <p className="mt-1 text-xs text-red-500">{cronError}</p>
                        )}
                      </>
                    ) : (
                      <p className="text-xs text-muted-foreground">
                        minute hour day month weekday
                      </p>
                    )}
                  </div>
                </div>
              </RadioGroup>

              <div className="flex items-start gap-2 rounded-md border bg-muted/50 p-3">
                <Clock className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <p className="text-xs text-muted-foreground">{scheduleSummary}</p>
              </div>

              <div className="mt-auto flex items-start justify-between gap-3 rounded-md border p-3">
                <div className="min-w-0">
                  <Label htmlFor="make-default" className="text-sm font-medium">
                    Make this the default
                  </Label>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {isFirstConfig
                      ? "The first pipeline is always the model's default."
                      : "The default pipeline is the one promoted runs are attached to."}
                  </p>
                </div>
                <Switch
                  id="make-default"
                  checked={makeDefault}
                  onCheckedChange={setMakeDefault}
                  disabled={isFirstConfig}
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConfigDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateConfig}
              loading={isSavingConfig}
              disabled={!selectedWorkflowId}
            >
              Create configuration
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create workflow */}
      <Dialog open={showCreateWorkflowDialog} onOpenChange={setShowCreateWorkflowDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create new workflow</DialogTitle>
            <DialogDescription>
              Creates an empty workflow you can then build out in the Workflow Studio
              (AI Agents → Workflow Studio).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <FormField id="new-workflow-name" label="Workflow name">
              <Input
                id="new-workflow-name"
                value={newWorkflowName}
                onChange={(e) => setNewWorkflowName(e.target.value)}
                placeholder="e.g. Churn model training"
                autoFocus
              />
            </FormField>
            <FormField id="new-workflow-description" label="Description (optional)">
              <Textarea
                id="new-workflow-description"
                value={newWorkflowDescription}
                onChange={(e) => setNewWorkflowDescription(e.target.value)}
                placeholder="What this training workflow does"
                rows={3}
              />
            </FormField>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateWorkflowDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateWorkflow}
              loading={isCreatingWorkflow}
              disabled={!newWorkflowName.trim()}
            >
              Create workflow
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Run details — full-height dialog with columns (Evaluations run-details style) */}
      <Dialog open={!!selectedRun} onOpenChange={(open) => !open && setSelectedRun(null)}>
        <DialogContent className="flex h-[90vh] max-h-[90vh] w-[95vw] max-w-[1800px] flex-col gap-0 overflow-hidden p-0">
          <DialogHeader className="shrink-0 border-b px-5 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <DialogTitle>Run Details #{selectedRun?.id?.slice(-6)}</DialogTitle>
                {selectedRun && isRunPromoted(selectedRun, model.pkl_file) && <PromotedBadge />}
              </div>
              {selectedRun && <RunStatusBadge status={selectedRun.status} />}
            </div>
            <DialogDescription className="text-xs">
              {selectedRun ? workflowName(selectedRun.workflow_id) : ""}
              {selectedRun?.started_at
                ? ` · ${formatDateTime(selectedRun.started_at)}`
                : ""}
            </DialogDescription>
          </DialogHeader>

          {/* Columns: run summary | artifacts | execution output */}
          <div className="min-h-0 flex-1">
            <ResizablePanelGroup
              direction="horizontal"
              autoSaveId="ml-pipeline-run-details"
              className="h-full"
            >
              {/* Summary column */}
              <ResizablePanel defaultSize={24} minSize={18} maxSize={35}>
                <div className="flex h-full flex-col overflow-hidden">
                  <div className="shrink-0 border-b px-4 py-2.5 text-sm font-medium">
                    Run Summary
                  </div>
                  <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
                    {selectedRun && (
                      <>
                        <Field label="Workflow">{workflowName(selectedRun.workflow_id)}</Field>
                        <Field label="Started">
                          <span className="text-muted-foreground">
                            {formatDateTime(selectedRun.started_at)}
                          </span>
                        </Field>
                        <Field label="Completed">
                          <span className="text-muted-foreground">
                            {formatDateTime(selectedRun.completed_at)}
                          </span>
                        </Field>
                        <Field label="Duration">
                          <span className="text-muted-foreground">
                            {formatRunDuration(
                              selectedRun.started_at,
                              selectedRun.completed_at
                            ) ?? "—"}
                          </span>
                        </Field>
                        <Field label="Pipeline">
                          {isRunDefaultPipeline(selectedRun, defaultConfigId)
                            ? "Model's default"
                            : "Not the default"}
                        </Field>
                        <Field label="Model file produced">
                          <span className="break-all font-mono text-xs text-muted-foreground">
                            {runModelFilePath(selectedRun) ?? "None"}
                          </span>
                        </Field>

                        {selectedRun.error_message && (
                          <div className="rounded-md border border-red-200 bg-red-50 p-3 dark:border-red-500/30 dark:bg-red-500/15">
                            <div className="mb-1 flex items-center gap-2 text-xs font-medium text-red-700 dark:text-red-400">
                              <AlertCircle className="h-4 w-4" />
                              Error
                            </div>
                            <p className="whitespace-pre-wrap break-words text-xs text-red-700 dark:text-red-400">
                              {selectedRun.error_message}
                            </p>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              </ResizablePanel>

              <ResizableHandle withHandle />

              {/* Artifacts column */}
              <ResizablePanel defaultSize={26} minSize={20}>
                <div className="flex h-full flex-col overflow-hidden">
                  <div className="flex shrink-0 items-center justify-between border-b px-4 py-2.5">
                    <span className="text-sm font-medium">Artifacts</span>
                    {artifacts.length > 0 && (
                      <Badge variant="secondary" className="text-[10px]">
                        {artifacts.length}
                      </Badge>
                    )}
                  </div>
                  <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
                    {artifactsQuery.isPending ? (
                      [0, 1, 2].map((i) => (
                        <Skeleton key={i} className="h-14 w-full rounded-md" />
                      ))
                    ) : artifacts.length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-8 text-center">
                        <FileCode className="mb-2 h-8 w-8 text-muted-foreground/40" />
                        <p className="text-sm text-muted-foreground">
                          This run produced no artifacts.
                        </p>
                      </div>
                    ) : (
                      artifacts.map((artifact) => {
                        const size = formatFileSize(artifact.file_size);
                        return (
                          <div
                            key={artifact.id}
                            className="flex items-center justify-between gap-2 rounded-md border p-2.5"
                          >
                            <div className="flex min-w-0 items-center gap-2">
                              <FileCode className="h-4 w-4 shrink-0 text-muted-foreground" />
                              <div className="min-w-0">
                                <p className="truncate text-sm font-medium">
                                  {artifact.artifact_name}
                                </p>
                                <p className="text-[11px] text-muted-foreground">
                                  {artifact.artifact_type.replace(/_/g, " ")}
                                  {size ? ` · ${size}` : ""}
                                </p>
                              </div>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 shrink-0"
                              aria-label={`Download ${artifact.artifact_name}`}
                              loading={downloadingArtifactId === artifact.id}
                              onClick={() => handleDownloadArtifact(artifact)}
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </ResizablePanel>

              <ResizableHandle withHandle />

              {/* Execution output column */}
              <ResizablePanel defaultSize={50} minSize={30}>
                <div className="flex h-full flex-col overflow-hidden">
                  <div className="shrink-0 border-b px-4 py-2.5 text-sm font-medium">
                    Execution output
                  </div>
                  <div className="min-h-0 flex-1 overflow-auto p-3">
                    {selectedRun?.execution_output ? (
                      <JsonViewer data={selectedRun.execution_output as JsonValue} />
                    ) : (
                      <div className="flex h-full flex-col items-center justify-center p-6 text-center">
                        <AlertCircle className="mb-3 h-10 w-10 text-muted-foreground/30" />
                        <p className="text-sm text-muted-foreground">
                          This run recorded no execution output.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </ResizablePanel>
            </ResizablePanelGroup>
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfig}
        isInProgress={isDeleting}
        itemName={
          configToDelete ? workflowName(configToDelete.workflow_id) : "configuration"
        }
        description="This action cannot be undone. This will permanently delete the pipeline configuration. Existing run history is kept."
      />
    </PageLayout>
  );
};

export default MLModelDetail;
