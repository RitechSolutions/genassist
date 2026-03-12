import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DataTable } from "@/components/DataTable";
import { TableCell, TableRow } from "@/components/table";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Loader2, Trash2 } from "lucide-react";
import { toast } from "react-hot-toast";
import { listLocalFineTuneJobs } from "@/services/localFineTune";
import type { LocalFineTuneJob } from "@/interfaces/localFineTune.interface";
import { formatStatusLabel } from "@/views/FineTune/utils/utils";

interface LocalFineTuneJobsCardProps {
  searchQuery: string;
  refreshKey?: number;
}

const inProgressStatuses = new Set(["running", "queued", "validating_files"]);

export function LocalFineTuneJobsCard({
  searchQuery,
  refreshKey = 0,
}: LocalFineTuneJobsCardProps) {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<LocalFineTuneJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [jobToDelete, setJobToDelete] = useState<LocalFineTuneJob | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    fetchJobs();
  }, [refreshKey]);

  const fetchJobs = async () => {
    try {
      setLoading(true);
      const data = await listLocalFineTuneJobs();
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
      [j.id, j.model, j.fine_tuned_model, j.status, j.training_file]
        .filter(Boolean)
        .map((v) => String(v).toLowerCase())
        .some((s) => s.includes(q))
    );
  }, [jobs, searchQuery]);

  const headers = [
    "Name",
    "Model",
    "Status",
    { label: "Action", className: "text-center pr-4" },
  ];

  const handleDelete = (job: LocalFineTuneJob) => {
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

  const renderStatus = (job: LocalFineTuneJob) => {
    const normalizedStatus = String(job.status ?? "").toLowerCase();
    const isInProgress = inProgressStatuses.has(normalizedStatus);

    if (isInProgress) {
      return (
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 text-primary animate-spin" />
          <span className="font-medium text-foreground capitalize">
            {formatStatusLabel(normalizedStatus)}
          </span>
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

  const renderActions = (job: LocalFineTuneJob) => (
    <Button
      variant="ghost"
      size="icon"
      className="h-8 w-8"
      onClick={(e) => {
        e.stopPropagation();
        handleDelete(job);
      }}
      title="Remove from list"
    >
      <Trash2 className="h-4 w-4 text-destructive" />
    </Button>
  );

  const renderRow = (job: LocalFineTuneJob) => {
    const name =
      job.fine_tuned_model || job.suffix || job.model || job.id || "—";
    return (
      <TableRow
        key={job.id}
        className="text-sm cursor-pointer hover:bg-muted/60"
        onClick={() => navigate(`/local-fine-tune/${job.id}`)}
      >
        <TableCell className="font-medium text-foreground">{name}</TableCell>
        <TableCell className="text-muted-foreground">{job.model || "—"}</TableCell>
        <TableCell className="min-w-[180px]">{renderStatus(job)}</TableCell>
        <TableCell
          className="w-[72px] text-center"
          onClick={(e) => e.stopPropagation()}
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
        emptyMessage="No Local Fine-Tune jobs found"
        searchEmptyMessage="No jobs matching your search"
      />

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isInProgress={isDeleting}
        itemName={jobToDelete?.id}
        title="Remove job from list?"
        description={`This will remove job "${jobToDelete?.id}" from the list. This action is local only.`}
        primaryButtonText="Remove"
        secondaryButtonText="Cancel"
        onCancel={() => setJobToDelete(null)}
      />
    </>
  );
}
