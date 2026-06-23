import React, { useEffect, useState } from "react";
import { toast } from "react-hot-toast";
import { Clock, Loader2, RefreshCw } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import JsonViewer from "@/components/JsonViewer";
import { getWorkflowScheduleRuns } from "@/services/workflowSchedules";
import {
  WorkflowSchedule,
  WorkflowScheduleRun,
  WorkflowScheduleRunStatus,
} from "@/interfaces/workflow-schedule.interface";

interface RunHistoryDialogProps {
  isOpen: boolean;
  onClose: () => void;
  schedule: WorkflowSchedule | null;
}

const statusVariant = (
  status: WorkflowScheduleRunStatus
): "default" | "secondary" | "destructive" | "outline" | "success" => {
  switch (status) {
    case "completed":
      return "success";
    case "failed":
      return "destructive";
    case "running":
      return "default";
    case "cancelled":
      return "outline";
    default:
      return "secondary";
  }
};

const formatDuration = (run: WorkflowScheduleRun): string | null => {
  if (!run.started_at || !run.completed_at) return null;
  const secs = Math.round(
    (new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000
  );
  if (secs < 60) return `${secs}s`;
  return `${Math.round(secs / 60)}m`;
};

const RunHistoryDialog: React.FC<RunHistoryDialogProps> = ({
  isOpen,
  onClose,
  schedule,
}) => {
  const [runs, setRuns] = useState<WorkflowScheduleRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchRuns = async () => {
    if (!schedule) return;
    try {
      setLoading(true);
      const data = await getWorkflowScheduleRuns(schedule.id, { limit: 50 });
      setRuns(data);
    } catch {
      toast.error("Failed to load run history");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && schedule) {
      fetchRuns();
      setExpandedId(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, schedule?.id]);

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between gap-2">
            <span>Run history — {schedule?.name}</span>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchRuns}
              disabled={loading}
              className="rounded-full"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </DialogTitle>
          <DialogDescription>
            Recent executions of this schedule.
          </DialogDescription>
        </DialogHeader>

        {loading && runs.length === 0 ? (
          <div className="flex items-center justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : runs.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            No runs yet.
          </p>
        ) : (
          <div className="divide-y rounded-md border">
            {runs.map((run) => {
              const duration = formatDuration(run);
              const expanded = expandedId === run.id;
              return (
                <div key={run.id} className="p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant={statusVariant(run.status)}>
                        {run.status}
                      </Badge>
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {run.started_at
                          ? new Date(run.started_at).toLocaleString()
                          : run.created_at
                          ? new Date(run.created_at).toLocaleString()
                          : "—"}
                      </span>
                      {duration && (
                        <span className="text-xs text-muted-foreground">
                          {duration}
                        </span>
                      )}
                    </div>
                    {(run.execution_output || run.error_message) && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          setExpandedId(expanded ? null : run.id)
                        }
                      >
                        {expanded ? "Hide" : "Details"}
                      </Button>
                    )}
                  </div>

                  {run.error_message && (
                    <div className="mt-2 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">
                      {run.error_message}
                    </div>
                  )}

                  {expanded && run.execution_output && (
                    <div className="mt-2 overflow-x-auto rounded border bg-muted/30 p-2">
                      <JsonViewer
                        data={run.execution_output as Record<string, unknown>}
                        collapsed
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default RunHistoryDialog;