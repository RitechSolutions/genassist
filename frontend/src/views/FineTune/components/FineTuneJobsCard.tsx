import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DataTable } from "@/components/DataTable";
import { TableCell, TableRow } from "@/components/table";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { formatCallDuration } from "@/helpers/formatters";
import {
  Loader2,
  Trash2,
} from "lucide-react";
import { toast } from "react-hot-toast";
import { listFineTuneJobs } from "@/services/openaiFineTune";
import type { FineTuneJob } from "@/interfaces/fineTune.interface";
import {
  formatStatusLabel,
  normalizePercent,
  normalizeSeconds,
  getAccuracyFromMetrics,
  inProgressStatuses,
} from "@/views/FineTune/utils/utils";
import type { FineTuneJobsCardProps, JobProgress } from "@/views/FineTune/types";

export function FineTuneJobsCard({ searchQuery, refreshKey = 0 }: FineTuneJobsCardProps) {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<FineTuneJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [jobToDelete, setJobToDelete] = useState<FineTuneJob | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    fetchJobs();
  }, [refreshKey]);

  const fetchJobs = async () => {
    try {
      setLoading(true);
      const data = await listFineTuneJobs();
      setJobs(data);
      setError(null);
    } catch (err) {
      setError("Failed to fetch jobs");
      toast.error("Failed to fetch jobs");
    } finally {
      setLoading(false);
    }
  };

  const filtered = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return jobs.filter((j) =>
      [j.id, j.suffix, j.model, j.fine_tuned_model, j.status]
        .filter(Boolean)
        .map((v) => String(v).toLowerCase())
        .some((s) => s.includes(q))
    );
  }, [jobs, searchQuery]);

  const headers = [
    "Name",
    "Model",
    "Status",
    "Accuracy",
    { label: "Action", className: "text-center pr-4" },
  ];

  const handleDelete = (job: FineTuneJob) => {
    setJobToDelete(job);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!jobToDelete) return;
    try {
      setIsDeleting(true);
      setJobs((prev) => prev.filter((j) => j.id !== jobToDelete.id));
      toast.success("Job removed from the list");
    } catch (err) {
      toast.error("Failed to delete job");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setJobToDelete(null);
    }
  };

  const renderStatus = (job: FineTuneJob) => {
    const progress = (job as Record<string, unknown>).progress as JobProgress | undefined;
    const normalizedStatus = String(job.status || progress?.status || "").toLowerCase();
    const isTerminalStatus = ["succeeded", "failed", "cancelled"].includes(normalizedStatus);
    const isInProgress =
      !isTerminalStatus && (inProgressStatuses.has(normalizedStatus) || progress?.is_running);
    const percent =
      normalizePercent((job as Record<string, unknown>).progress_percentage) ??
      normalizePercent(progress?.progress_percentage);
    const estimatedSeconds =
      normalizeSeconds((job as Record<string, unknown>).estimated_seconds_remaining) ??
      normalizeSeconds(progress?.estimated_seconds_remaining);
    const subLabel =
      progress?.message ||
      (job as Record<string, unknown>).message ||
      (job as Record<string, unknown>).error_message;
    const progressLabel =
      typeof percent === "number" ? `${percent} %` : formatStatusLabel(normalizedStatus);
    const etaLabel =
      typeof estimatedSeconds === "number"
        ? `${formatCallDuration(estimatedSeconds)} left`
        : null;

    if (isInProgress) {
      return (
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 text-primary animate-spin" />
          <div className="flex flex-col leading-tight">
            <span className="font-medium text-foreground flex items-center gap-1">
              {progressLabel}
              {etaLabel && (
                <span className="text-xs font-normal text-muted-foreground whitespace-nowrap">
                  ({etaLabel})
                </span>
              )}
            </span>
            {subLabel && (
              <span className="text-xs text-muted-foreground">{String(subLabel)}</span>
            )}
          </div>
        </div>
      );
    }

    if (normalizedStatus === "succeeded") {
      return (
        <Badge variant="outline" className="px-3 py-1 text-xs font-medium">
          Completed
        </Badge>
      );
    }

    if (normalizedStatus === "cancelled") {
      return (
        <Badge
          variant="secondary"
          className="px-3 py-1 text-xs font-medium bg-muted text-muted-foreground"
        >
          Cancelled
        </Badge>
      );
    }

    if (normalizedStatus === "failed") {
      return (
        <Badge variant="destructive" className="px-3 py-1 text-xs font-medium">
          Failed
        </Badge>
      );
    }

    return (
      <Badge variant="outline" className="px-3 py-1 text-xs font-medium capitalize">
        {formatStatusLabel(normalizedStatus)}
      </Badge>
    );
  };

  const renderAccuracy = (job: FineTuneJob) => {
    const progress = (job as Record<string, unknown>).progress as JobProgress | undefined;
    const normalizedStatus = String(job.status || progress?.status || "").toLowerCase();
    const isTerminalStatus = ["succeeded", "failed", "cancelled"].includes(normalizedStatus);
    const isInProgress =
      !isTerminalStatus && (inProgressStatuses.has(normalizedStatus) || progress?.is_running);
    const latestMetricsAccuracy = getAccuracyFromMetrics(progress?.latest_metrics, isInProgress);
    const accuracy =
      normalizePercent((job as Record<string, unknown>).accuracy) ??
      normalizePercent((job as Record<string, unknown>).validation_accuracy) ??
      normalizePercent((job as Record<string, unknown>).full_valid_mean_token_accuracy) ??
      normalizePercent(progress?.accuracy) ??
      latestMetricsAccuracy;

    if (accuracy === null) {
      if (isInProgress) {
        return (
          <div className="flex items-center">
            <Loader2 className="h-4 w-4 text-primary animate-spin" />
          </div>
        );
      }
      return <span className="text-sm text-muted-foreground">—</span>;
    }

    return (
      <div className="flex items-center gap-2">
        {isInProgress && <Loader2 className="h-4 w-4 text-primary animate-spin" />}
        <span className="text-sm font-medium text-foreground">{accuracy} %</span>
      </div>
    );
  };

  const renderActions = (job: FineTuneJob) => {
    return (
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        onClick={(e) => {
          e.stopPropagation();
          handleDelete(job);
        }}
        title="Delete job"
      >
        <Trash2 className="h-4 w-4 text-destructive" />
      </Button>
    );
  };

  const renderRow = (job: FineTuneJob) => {
    const jobIdentifier = job.id || job.openai_job_id;
    const handleRowClick = () => {
      if (!jobIdentifier) return;
      navigate(`/fine-tune/${jobIdentifier}`);
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTableRowElement>) => {
      if (!jobIdentifier) return;
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        navigate(`/fine-tune/${jobIdentifier}`);
      }
    };

    return (
      <TableRow
        key={job.id}
        className="text-sm cursor-pointer hover:bg-muted/60 focus-within:bg-muted/60"
        onClick={handleRowClick}
        onKeyDown={handleKeyDown}
        tabIndex={0}
      >
        <TableCell className="font-medium text-foreground">
          {job.suffix || job.fine_tuned_model || job.id || "—"}
        </TableCell>
        <TableCell className="text-muted-foreground">{job.model || "—"}</TableCell>
        <TableCell className="min-w-[180px]">{renderStatus(job)}</TableCell>
        <TableCell className="min-w-[140px]">{renderAccuracy(job)}</TableCell>
        <TableCell
          className="w-[72px] text-center"
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
        >
          {renderActions(job)}
        </TableCell>
      </TableRow>
    );
  };

  return (
    <>
      <DataTable
        data={filtered}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        headers={headers}
        renderRow={renderRow}
        emptyMessage="No Fine-Tune jobs found"
        searchEmptyMessage="No jobs matching your search"
      />

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isInProgress={isDeleting}
        itemName={jobToDelete?.suffix || jobToDelete?.id}
        title="Delete fine-tune job?"
        description={`This action cannot be undone. This will remove job "${jobToDelete?.suffix || jobToDelete?.id}".`}
        primaryButtonText="Delete"
        secondaryButtonText="Cancel"
        onCancel={() => setJobToDelete(null)}
      />
    </>
  );
}