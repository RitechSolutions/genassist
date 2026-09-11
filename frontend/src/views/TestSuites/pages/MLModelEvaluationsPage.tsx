import React, { useEffect, useMemo, useState } from "react";
import { toast } from "react-hot-toast";
import { BarChart3, Loader2, Scale, Trash2 } from "lucide-react";

import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Checkbox } from "@/components/checkbox";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/dialog";
import { PageListSkeleton } from "@/components/skeletons";

import { deleteMLModel, getAllMLModels } from "@/services/mlModels";
import { getModelPipelineRuns } from "@/services/mlModelPipelines";
import { MLModel } from "@/interfaces/ml-model.interface";
import { modelTypeLabel as getModelTypeLabel } from "@/views/MLModels/helpers/modelTypes";

interface RegressionMetrics {
  rmse?: number;
  mae?: number;
  r2_score?: number;
  mse?: number;
}

interface ClassificationMetrics {
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1_score?: number;
}

type TaskType = "regression" | "classification";

interface EvaluationResult {
  model: MLModel;
  taskType: TaskType | null;
  metrics: RegressionMetrics & ClassificationMetrics;
}

function extractMetrics(
  executionOutput: Record<string, unknown> | undefined
): { taskType: TaskType | null; metrics: RegressionMetrics & ClassificationMetrics } {
  const output = (executionOutput?.output ?? {}) as Record<string, unknown>;
  const metrics = (output.metrics ?? {}) as Record<string, unknown>;

  if (typeof metrics.accuracy === "number") {
    return {
      taskType: "classification",
      metrics: {
        accuracy: metrics.accuracy as number,
        precision: metrics.precision as number | undefined,
        recall: metrics.recall as number | undefined,
        f1_score: metrics.f1_score as number | undefined,
      },
    };
  }

  if (typeof metrics.mse === "number" || typeof metrics.r2_score === "number") {
    const mse = metrics.mse as number | undefined;
    const rmse = typeof metrics.rmse === "number" ? (metrics.rmse as number) : mse !== undefined ? Math.sqrt(mse) : undefined;
    return {
      taskType: "regression",
      metrics: {
        mse,
        rmse,
        mae: metrics.mae as number | undefined,
        r2_score: metrics.r2_score as number | undefined,
      },
    };
  }

  return { taskType: null, metrics: {} };
}

function formatMetric(value: number | undefined): string {
  return value === undefined ? "—" : value.toFixed(4);
}

type QualityLabel = "Excellent" | "Good" | "Fair" | "Poor";

// R² and F1/accuracy are both unitless 0-1 scores (higher = better), so the same
// band thresholds give a consistent read across model types — unlike RMSE/MAE,
// which are in the target variable's own units and can't be compared across models.
function getQualityRating(
  taskType: TaskType | null,
  metrics: RegressionMetrics & ClassificationMetrics
): { label: QualityLabel; score: number } | null {
  if (taskType === "regression") {
    const score = metrics.r2_score;
    if (score === undefined) return null;
    if (score >= 0.9) return { label: "Excellent", score };
    if (score >= 0.7) return { label: "Good", score };
    if (score >= 0.5) return { label: "Fair", score };
    return { label: "Poor", score };
  }
  if (taskType === "classification") {
    const score = metrics.f1_score ?? metrics.accuracy;
    if (score === undefined) return null;
    if (score >= 0.9) return { label: "Excellent", score };
    if (score >= 0.75) return { label: "Good", score };
    if (score >= 0.6) return { label: "Fair", score };
    return { label: "Poor", score };
  }
  return null;
}

function QualityBadge({ label }: { label: QualityLabel }) {
  const styles: Record<QualityLabel, string> = {
    Excellent: "border-transparent bg-green-600 text-white hover:bg-green-600/80",
    Good: "border-transparent bg-blue-600 text-white hover:bg-blue-600/80",
    Fair: "border-transparent bg-amber-500 text-white hover:bg-amber-500/80",
    Poor: "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
  };
  return <Badge className={styles[label]}>{label}</Badge>;
}

interface RankedModel {
  model: MLModel;
  taskType: TaskType;
  metrics: RegressionMetrics & ClassificationMetrics;
  quality: QualityLabel;
  score: number;
  rankInGroup: number;
}

const MLModelEvaluationsPage: React.FC = () => {
  const [models, setModels] = useState<MLModel[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [result, setResult] = useState<EvaluationResult | null>(null);
  const [evaluateError, setEvaluateError] = useState<string | null>(null);
  const [rankings, setRankings] = useState<RankedModel[]>([]);
  const [isLoadingRankings, setIsLoadingRankings] = useState(false);
  const [rankingsError, setRankingsError] = useState<string | null>(null);
  const [modelPendingDelete, setModelPendingDelete] = useState<MLModel | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isCompareOpen, setIsCompareOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setIsLoading(true);
      setHasError(false);
      try {
        const data = await getAllMLModels();
        if (!cancelled) setModels(data);
      } catch {
        if (!cancelled) setHasError(true);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (models.length === 0) return;
    let cancelled = false;

    const loadRankings = async () => {
      setIsLoadingRankings(true);
      setRankingsError(null);
      try {
        const perModel = await Promise.all(
          models.map(async (model) => {
            const runs = await getModelPipelineRuns(model.id);
            const latestCompleted = runs.find((run) => run.status === "completed");
            if (!latestCompleted) return null;
            const { taskType, metrics } = extractMetrics(latestCompleted.execution_output);
            if (!taskType) return null;
            const rating = getQualityRating(taskType, metrics);
            if (!rating) return null;
            return { model, taskType, metrics, quality: rating.label, score: rating.score };
          })
        );
        if (cancelled) return;

        const sorted = perModel
          .filter((r): r is Omit<RankedModel, "rankInGroup"> => r !== null)
          .sort((a, b) => {
            if (a.taskType !== b.taskType) return a.taskType.localeCompare(b.taskType);
            return b.score - a.score;
          });

        const groupCounts: Partial<Record<TaskType, number>> = {};
        const ranked: RankedModel[] = sorted.map((entry) => {
          groupCounts[entry.taskType] = (groupCounts[entry.taskType] ?? 0) + 1;
          return { ...entry, rankInGroup: groupCounts[entry.taskType]! };
        });
        setRankings(ranked);
      } catch (error) {
        if (!cancelled) {
          setRankingsError(error instanceof Error ? error.message : "Failed to load model rankings.");
        }
      } finally {
        if (!cancelled) setIsLoadingRankings(false);
      }
    };
    void loadRankings();
    return () => {
      cancelled = true;
    };
  }, [models]);

  const filteredModels = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return models;
    return models.filter((m) => m.name.toLowerCase().includes(query));
  }, [models, searchQuery]);

  const toggleSelected = (modelId: string) => {
    setSelectedIds((prev) =>
      prev.includes(modelId) ? prev.filter((id) => id !== modelId) : [...prev, modelId]
    );
  };

  const handleDelete = async () => {
    if (!modelPendingDelete) return;
    setIsDeleting(true);
    try {
      await deleteMLModel(modelPendingDelete.id);
      setModels((prev) => prev.filter((m) => m.id !== modelPendingDelete.id));
      setSelectedIds((prev) => prev.filter((id) => id !== modelPendingDelete.id));
      setRankings((prev) => prev.filter((r) => r.model.id !== modelPendingDelete.id));
      if (result?.model.id === modelPendingDelete.id) setResult(null);
      setModelPendingDelete(null);
    } catch {
      toast.error("Failed to delete ML model.");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleEvaluate = async () => {
    const model = models.find((m) => m.id === selectedIds[0]);
    if (!model) return;

    setIsEvaluating(true);
    setEvaluateError(null);
    setResult(null);
    try {
      const runs = await getModelPipelineRuns(model.id);
      const latestCompleted = runs.find((run) => run.status === "completed");
      if (!latestCompleted) {
        setResult({ model, taskType: null, metrics: {} });
        return;
      }
      const { taskType, metrics } = extractMetrics(latestCompleted.execution_output);
      setResult({ model, taskType, metrics });
    } catch (error) {
      setEvaluateError(error instanceof Error ? error.message : "Failed to fetch pipeline runs for this model.");
    } finally {
      setIsEvaluating(false);
    }
  };

  return (
    <PageLayout>
      <PageHeader
        title="Evaluate ML models"
        subtitle="Select a model to view the metrics captured during its last training run."
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search models..."
      />

      <div className="rounded-lg border bg-card dark:bg-zinc-900 overflow-hidden">
        <div className="px-6 py-3 border-b bg-muted text-sm font-semibold">Model rankings</div>
        {isLoadingRankings ? (
          <PageListSkeleton variant="standard" bordered={false} />
        ) : rankingsError ? (
          <div className="px-6 py-4 text-sm text-destructive">Couldn't load rankings: {rankingsError}</div>
        ) : rankings.length === 0 ? (
          <div className="px-6 py-4 text-sm text-muted-foreground">
            No models with a completed training run yet — rankings appear once at least one model has trained
            successfully.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted text-left text-xs font-medium text-muted-foreground">
                  <th className="px-6 py-3 font-medium w-10">#</th>
                  <th className="px-6 py-3 font-medium">Model</th>
                  <th className="px-6 py-3 font-medium">Task</th>
                  <th className="px-6 py-3 font-medium">Primary metric</th>
                  <th className="px-6 py-3 font-medium">Quality</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rankings.map((entry, index) => {
                  const isNewGroup = index > 0 && rankings[index - 1].taskType !== entry.taskType;
                  return (
                    <tr key={entry.model.id} className={isNewGroup ? "border-t-2 border-border" : ""}>
                      <td className="px-6 py-4 text-muted-foreground">{entry.rankInGroup}</td>
                      <td className="px-6 py-4 font-medium">{entry.model.name}</td>
                      <td className="px-6 py-4">
                        <Badge variant="secondary">
                          {entry.taskType === "regression" ? "Regression" : "Classification"}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-muted-foreground">
                        {entry.taskType === "regression"
                          ? `R² = ${formatMetric(entry.metrics.r2_score)}`
                          : `F1 = ${formatMetric(entry.metrics.f1_score ?? entry.metrics.accuracy)}`}
                      </td>
                      <td className="px-6 py-4">
                        <QualityBadge label={entry.quality} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {selectedIds.length === 0
            ? "No model selected"
            : `${selectedIds.length} model${selectedIds.length > 1 ? "s" : ""} selected`}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => setIsCompareOpen(true)}
            disabled={selectedIds.length < 2}
          >
            <Scale className="h-4 w-4 mr-2" />
            Compare models
          </Button>
          <Button onClick={handleEvaluate} disabled={selectedIds.length !== 1 || isEvaluating}>
            {isEvaluating ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Evaluating…
              </>
            ) : (
              "Evaluate model"
            )}
          </Button>
        </div>
      </div>

      <div className="rounded-lg border bg-card dark:bg-zinc-900 overflow-hidden">
        {isLoading ? (
          <PageListSkeleton variant="standard" bordered={false} />
        ) : hasError ? (
          <div className="py-16 text-center">
            <p className="text-sm text-muted-foreground mb-3">Couldn't load ML models.</p>
          </div>
        ) : filteredModels.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
            <div className="rounded-full bg-muted p-4">
              <BarChart3 className="h-12 w-12 text-muted-foreground" />
            </div>
            <h3 className="font-medium text-lg">No ML models found</h3>
            <p className="text-sm text-muted-foreground max-w-sm">
              {searchQuery
                ? "No models match your search."
                : "Add an ML model under Connect > ML Models to evaluate it here."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted text-left text-xs font-medium text-muted-foreground">
                  <th className="px-6 py-3 font-medium w-10" />
                  <th className="px-6 py-3 font-medium">Model</th>
                  <th className="px-6 py-3 font-medium">Type</th>
                  <th className="px-6 py-3 font-medium">Target variable</th>
                  <th className="px-6 py-3 font-medium">Features</th>
                  <th className="px-6 py-3 font-medium w-10" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredModels.map((model) => (
                  <tr
                    key={model.id}
                    className="hover:bg-muted transition-colors cursor-pointer"
                    onClick={() => toggleSelected(model.id)}
                  >
                    <td className="px-6 py-4" onClick={(e) => e.stopPropagation()}>
                      <Checkbox
                        checked={selectedIds.includes(model.id)}
                        onCheckedChange={() => toggleSelected(model.id)}
                        id={`model-${model.id}`}
                      />
                    </td>
                    <td className="px-6 py-4 font-medium">{model.name}</td>
                    <td className="px-6 py-4">
                      <Badge variant="secondary">{getModelTypeLabel(model.model_type)}</Badge>
                    </td>
                    <td className="px-6 py-4 text-muted-foreground">{model.target_variable}</td>
                    <td className="px-6 py-4 text-muted-foreground">{model.features?.length ?? 0}</td>
                    <td className="px-6 py-4" onClick={(e) => e.stopPropagation()}>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Delete ${model.name}`}
                        onClick={() => setModelPendingDelete(model)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {evaluateError && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-6 py-4 text-sm text-destructive">
          Couldn't evaluate this model: {evaluateError}
        </div>
      )}

      {result && (
        <div className="rounded-lg border bg-card dark:bg-zinc-900 overflow-hidden">
          <div className="px-6 py-3 border-b bg-muted text-sm font-semibold flex items-center gap-2">
            {result.model.name}
            <Badge variant="secondary">{getModelTypeLabel(result.model.model_type)}</Badge>
            {(() => {
              const rating = getQualityRating(result.taskType, result.metrics);
              return rating ? <QualityBadge label={rating.label} /> : null;
            })()}
          </div>

          {result.taskType === "regression" && (
            <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-border">
              <MetricTile label="RMSE" value={formatMetric(result.metrics.rmse)} />
              <MetricTile label="MAE" value={formatMetric(result.metrics.mae)} />
              <MetricTile label="R²" value={formatMetric(result.metrics.r2_score)} />
              <MetricTile label="MSE" value={formatMetric(result.metrics.mse)} />
            </div>
          )}

          {result.taskType === "classification" && (
            <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-border">
              <MetricTile label="Accuracy" value={formatMetric(result.metrics.accuracy)} />
              <MetricTile label="Precision" value={formatMetric(result.metrics.precision)} />
              <MetricTile label="Recall" value={formatMetric(result.metrics.recall)} />
              <MetricTile label="F1" value={formatMetric(result.metrics.f1_score)} />
            </div>
          )}

          {result.taskType === null && (
            <div className="px-6 py-4 text-sm text-muted-foreground">
              No training metrics available for this model — it has no completed training pipeline run yet.
            </div>
          )}
        </div>
      )}

      <ConfirmDialog
        isOpen={!!modelPendingDelete}
        onOpenChange={(open) => {
          if (!open) setModelPendingDelete(null);
        }}
        onConfirm={handleDelete}
        isInProgress={isDeleting}
        itemName={modelPendingDelete?.name ?? ""}
        title="Delete ML model"
      />

      <CompareModelsDialog
        isOpen={isCompareOpen}
        onOpenChange={setIsCompareOpen}
        models={models.filter((m) => selectedIds.includes(m.id))}
        rankings={rankings}
      />
    </PageLayout>
  );
};

function CompareModelsDialog({
  isOpen,
  onOpenChange,
  models,
  rankings,
}: {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  models: MLModel[];
  rankings: RankedModel[];
}) {
  const rows: Array<{ label: string; get: (m: RegressionMetrics & ClassificationMetrics) => string }> = [
    { label: "RMSE", get: (m) => formatMetric(m.rmse) },
    { label: "MAE", get: (m) => formatMetric(m.mae) },
    { label: "R²", get: (m) => formatMetric(m.r2_score) },
    { label: "MSE", get: (m) => formatMetric(m.mse) },
    { label: "Accuracy", get: (m) => formatMetric(m.accuracy) },
    { label: "Precision", get: (m) => formatMetric(m.precision) },
    { label: "Recall", get: (m) => formatMetric(m.recall) },
    { label: "F1", get: (m) => formatMetric(m.f1_score) },
  ];

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Compare models</DialogTitle>
        </DialogHeader>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs font-medium text-muted-foreground">
                <th className="py-2 pr-4 font-medium">Metric</th>
                {models.map((model) => (
                  <th key={model.id} className="py-2 px-4 font-medium">
                    <div className="flex flex-col gap-1">
                      <span className="text-foreground">{model.name}</span>
                      {(() => {
                        const entry = rankings.find((r) => r.model.id === model.id);
                        return entry ? <QualityBadge label={entry.quality} /> : <Badge variant="secondary">No data</Badge>;
                      })()}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((row) => {
                const values = models.map((model) => {
                  const entry = rankings.find((r) => r.model.id === model.id);
                  return entry ? row.get(entry.metrics) : "—";
                });
                if (values.every((v) => v === "—")) return null;
                return (
                  <tr key={row.label}>
                    <td className="py-2 pr-4 text-muted-foreground">{row.label}</td>
                    {values.map((value, i) => (
                      <td key={models[i].id} className="py-2 px-4 font-medium">
                        {value}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="px-6 py-4">
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

export default MLModelEvaluationsPage;
