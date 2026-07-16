import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DataTable, Column } from "@/components/ui/data-table";
import { LIST_PAGE_SIZE } from "@/constants/pagination";
import { ListEmptyState } from "@/components/ListEmptyState";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Loader2, Trash2, Sparkles, Plus, RefreshCw, Ban } from "lucide-react";
import { toast } from "react-hot-toast";
import {
  listBedrockFineTuneJobs,
  syncBedrockFineTuneJobs,
  deleteBedrockFineTuneJob,
  cancelBedrockFineTuneJob,
} from "@/services/bedrockFineTune";
import type { BedrockFineTuneJob } from "@/interfaces/bedrockFineTune.interface";
import {
  bedrockInProgressStatuses,
  bedrockTerminalStatuses,
  formatBedrockStatusLabel,
} from "@/views/BedrockFineTune/utils/utils";
import type { BedrockFineTuneJobsCardProps } from "@/views/BedrockFineTune/types";

export function BedrockFineTuneJobsCard({
  searchQuery,
  refreshKey = 0,
  onNewFineTuneJob,
}: BedrockFineTuneJobsCardProps) {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<BedrockFineTuneJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobToDelete, setJobToDelete] = useState<BedrockFineTuneJob | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [jobToCancel, setJobToCancel] = useState<BedrockFineTuneJob | null>(null);
  const [isCancelDialogOpen, setIsCancelDialogOpen] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);

  useEffect(() => {
    fetchJobs();
  }, [refreshKey]);

  const fetchJobs = async () => {
    try {
      setLoading(true);
      // Fast cached load — no sync. Press "Sync" to refresh status from Bedrock.
      const data = await listBedrockFineTuneJobs();
      setJobs(data);
      setError(null);
    } catch (err) {
      setError("Failed to fetch jobs");
      toast.error("Failed to fetch jobs");
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    try {
      setSyncing(true);
      const data = await syncBedrockFineTuneJobs();
      setJobs(data);
      setError(null);
      toast.success("Jobs synced");
    } catch (err) {
      toast.error("Failed to sync jobs");
    } finally {
      setSyncing(false);
    }
  };

  const filtered = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return jobs.filter((j) =>
      [j.id, j.suffix, j.custom_model_name, j.base_model_id, j.status, j.deployment_status]
        .filter(Boolean)
        .map((v) => String(v).toLowerCase())
        .some((s) => s.includes(q))
    );
  }, [jobs, searchQuery]);

  const handleDelete = (job: BedrockFineTuneJob) => {
    setJobToDelete(job);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!jobToDelete) return;
    try {
      setIsDeleting(true);
      await deleteBedrockFineTuneJob(jobToDelete.id);
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

  const handleCancel = (job: BedrockFineTuneJob) => {
    setJobToCancel(job);
    setIsCancelDialogOpen(true);
  };

  const handleCancelConfirm = async () => {
    if (!jobToCancel) return;
    try {
      setIsCancelling(true);
      const updated = await cancelBedrockFineTuneJob(jobToCancel.id);
      if (updated) {
        setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
      }
      toast.success("Job cancellation requested");
    } catch (err) {
      toast.error("Failed to cancel job");
    } finally {
      setIsCancelling(false);
      setIsCancelDialogOpen(false);
      setJobToCancel(null);
    }
  };

  const renderStatus = (job: BedrockFineTuneJob) => {
    const normalizedStatus = String(job.status || "").toLowerCase();
    const isInProgress = bedrockInProgressStatuses.has(normalizedStatus);

    if (isInProgress) {
      return (
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 text-primary animate-spin" />
          <span className="font-medium text-foreground">
            {formatBedrockStatusLabel(String(job.status || ""))}
          </span>
        </div>
      );
    }

    if (normalizedStatus === "completed") {
      return (
        <Badge variant="outline" className="px-3 py-1 text-xs font-medium">
          Completed
        </Badge>
      );
    }

    if (normalizedStatus === "stopped") {
      return (
        <Badge
          variant="secondary"
          className="px-3 py-1 text-xs font-medium bg-muted text-muted-foreground"
        >
          Stopped
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
        {formatBedrockStatusLabel(normalizedStatus)}
      </Badge>
    );
  };

  const renderDeployment = (job: BedrockFineTuneJob) => {
    const status = String(job.deployment_status || "NotDeployed").toLowerCase();

    if (status === "active") {
      return (
        <Badge variant="outline" className="px-3 py-1 text-xs font-medium border-success text-success">
          Active
        </Badge>
      );
    }
    if (status === "creating") {
      return (
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 text-primary animate-spin" />
          <span className="text-sm text-muted-foreground">Creating</span>
        </div>
      );
    }
    if (status === "failed") {
      return (
        <Badge variant="destructive" className="px-3 py-1 text-xs font-medium">
          Failed
        </Badge>
      );
    }
    return <span className="text-sm text-muted-foreground">Not deployed</span>;
  };

  const renderActions = (job: BedrockFineTuneJob) => {
    const normalizedStatus = String(job.status || "").toLowerCase();
    const canCancel = normalizedStatus === "inprogress";
    const canDelete = bedrockTerminalStatuses.has(normalizedStatus);

    return (
      <div className="flex items-center justify-center gap-1">
        {canCancel && (
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={(e) => {
              e.stopPropagation();
              handleCancel(job);
            }}
            title="Cancel job"
          >
            <Ban className="h-4 w-4 text-warning" />
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          disabled={!canDelete}
          onClick={(e) => {
            e.stopPropagation();
            handleDelete(job);
          }}
          title={
            canDelete
              ? "Delete job"
              : "Cancel or wait for the job to finish before deleting"
          }
        >
          <Trash2 className="h-4 w-4 text-destructive" />
        </Button>
      </div>
    );
  };

  const columns: Column<BedrockFineTuneJob>[] = [
    {
      header: "Name",
      key: "name",
      className: "font-medium text-foreground",
      cell: (job) => job.suffix || job.custom_model_name || job.id || "—",
    },
    {
      header: "Base Model",
      key: "base_model",
      className: "text-muted-foreground",
      cell: (job) => job.base_model_id || "—",
    },
    {
      header: "Status",
      key: "status",
      className: "min-w-[160px]",
      cell: (job) => renderStatus(job),
    },
    {
      header: "Deployment",
      key: "deployment",
      className: "min-w-[140px]",
      cell: (job) => renderDeployment(job),
    },
    {
      header: "Action",
      key: "action",
      headerClassName: "text-center pr-4 whitespace-nowrap",
      className: "w-[72px] text-center",
      cell: (job) => (
        <div
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
        >
          {renderActions(job)}
        </div>
      ),
    },
  ];

  const handleRowClick = (job: BedrockFineTuneJob) => {
    if (!job.id) return;
    navigate(`/bedrock-fine-tune/${job.id}`);
  };

  const isSearchActive = searchQuery.trim().length > 0;

  const emptyState = useMemo(
    () => (
      <ListEmptyState
        icon={<Sparkles className="h-12 w-12 text-gray-400" />}
        title={
          isSearchActive
            ? "No matching fine-tune jobs"
            : "No fine-tune jobs yet"
        }
        description={
          isSearchActive
            ? "Try adjusting your search query."
            : "Start a job to fine-tune an Amazon Nova model on your data. Jobs you create will show up here."
        }
        action={
          !isSearchActive && onNewFineTuneJob ? (
            <Button
              onClick={onNewFineTuneJob}
              className="rounded-full flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              New Fine-Tune Job
            </Button>
          ) : undefined
        }
      />
    ),
    [isSearchActive, onNewFineTuneJob]
  );

  return (
    <>
      <div className="flex justify-end mb-3">
        <Button
          variant="outline"
          size="sm"
          onClick={handleSync}
          disabled={syncing || loading}
        >
          {syncing ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4 mr-2" />
          )}
          Sync
        </Button>
      </div>

      <DataTable
        data={filtered}
        columns={columns}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        pageSize={LIST_PAGE_SIZE}
        onRowClick={handleRowClick}
        emptyMessage="No Bedrock fine-tune jobs found"
        notFoundMessage="No jobs matching your search"
        emptyState={emptyState}
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

      <ConfirmDialog
        isOpen={isCancelDialogOpen}
        onOpenChange={setIsCancelDialogOpen}
        onConfirm={handleCancelConfirm}
        isInProgress={isCancelling}
        itemName={jobToCancel?.suffix || jobToCancel?.id}
        title="Cancel fine-tune job?"
        description={`This stops the running job on AWS Bedrock. Job "${jobToCancel?.suffix || jobToCancel?.id}" cannot be resumed once cancelled.`}
        primaryButtonText="Cancel Job"
        secondaryButtonText="Keep Running"
        onCancel={() => setJobToCancel(null)}
      />
    </>
  );
}
