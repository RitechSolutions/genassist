import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DataTable, type Column } from "@/components/ui/data-table";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Loader2, Trash2 } from "lucide-react";
import { toast } from "react-hot-toast";
import type { LocalFineTuneJob } from "@/interfaces/localFineTune.interface";
import { formatStatusLabel, inProgressStatuses } from "@/views/FineTune/utils/utils";
import {
  getLocalFineTuneJobDisplayName,
  getLocalFineTuneJobNameSubtitle,
} from "@/views/LocalFineTune/utils/jobDisplayName";

function formatShortDate(value: unknown): string {
  if (value == null || value === "") return "—";
  const d = new Date(String(value));
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function renderLocalJobStatus(job: LocalFineTuneJob) {
  const normalizedStatus = String(job.status ?? "").toLowerCase();
  const isInProgress = inProgressStatuses.has(normalizedStatus);

  if (isInProgress) {
    return (
      <div className="flex items-center gap-2">
        <Loader2 className="h-4 w-4 text-primary animate-spin shrink-0" />
        <span className="font-medium text-foreground capitalize">
          {formatStatusLabel(normalizedStatus)}
        </span>
      </div>
    );
  }

  if (normalizedStatus === "succeeded") {
    return (
      <Badge variant="outline" className="px-3 py-1 text-xs font-medium border-teal-200 bg-teal-50 text-teal-800">
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
}

interface LocalFineTuneJobsCardProps {
  jobs: LocalFineTuneJob[];
  setJobs: React.Dispatch<React.SetStateAction<LocalFineTuneJob[]>>;
  loading: boolean;
  error: string | null;
  searchQuery: string;
}

export function LocalFineTuneJobsCard({
  jobs,
  setJobs,
  loading,
  error,
  searchQuery,
}: LocalFineTuneJobsCardProps) {
  const navigate = useNavigate();
  const [jobToDelete, setJobToDelete] = useState<LocalFineTuneJob | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const filtered = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return jobs.filter((j) =>
      [j.id, j.model, j.fine_tuned_model, j.status, j.training_file, j.suffix]
        .filter(Boolean)
        .map((v) => String(v).toLowerCase())
        .some((s) => s.includes(q))
    );
  }, [jobs, searchQuery]);

  const columns = useMemo<Column<LocalFineTuneJob>[]>(
    () => [
      {
        header: "Name",
        key: "name",
        cell: (job) => {
          const primary = getLocalFineTuneJobDisplayName(job);
          const secondary = getLocalFineTuneJobNameSubtitle(job, primary);
          return (
            <div className="flex flex-col gap-0.5 min-w-0">
              <span className="font-medium text-zinc-800 truncate">{primary}</span>
              {secondary ? (
                <span className="text-xs text-muted-foreground truncate">{secondary}</span>
              ) : null}
            </div>
          );
        },
      },
      {
        header: "Base model",
        key: "model",
        cell: (job) => (
          <span className="text-sm text-muted-foreground line-clamp-2">
            {job.model || "—"}
          </span>
        ),
      },
      {
        header: "Created",
        key: "created_at",
        cell: (job) => (
          <span className="text-xs text-zinc-500 tabular-nums">
            {formatShortDate(job.created_at)}
          </span>
        ),
      },
      {
        header: "Status",
        key: "status",
        cell: (job) => renderLocalJobStatus(job),
      },
      // {
      //   header: "",
      //   key: "actions",
      //   cell: (job) => (
      //     <Button
      //       variant="ghost"
      //       size="icon"
      //       className="h-8 w-8"
      //       onClick={(e) => {
      //         e.stopPropagation();
      //         setJobToDelete(job);
      //         setIsDeleteDialogOpen(true);
      //       }}
      //       title="Remove from list"
      //     >
      //       <Trash2 className="h-4 w-4 text-destructive" />
      //     </Button>
      //   ),
      // },
    ],
    []
  );

  const handleDeleteConfirm = async () => {
    if (!jobToDelete) return;
    try {
      setIsDeleting(true);
      setJobs((prev) => prev.filter((j) => j.id !== jobToDelete.id));
      toast.success("Job removed from the list");
    } catch {
      toast.error("Failed to delete job");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setJobToDelete(null);
    }
  };

  return (
    <>
      <DataTable
        data={filtered}
        columns={columns}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        emptyMessage="No Local Fine-Tune jobs found"
        notFoundMessage="No jobs matching your search"
        keyExtractor={(job) => job.id}
        pageSize={10}
        onRowClick={(job) => navigate(`/local-fine-tune/${job.id}`)}
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
