import React, { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "react-hot-toast";
import {
  Plus,
  Pencil,
  Trash2,
  Play,
  History,
  CalendarClock,
  MoreVertical,
  ArrowLeft,
} from "lucide-react";

import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { Switch } from "@/components/switch";
import { SearchInput } from "@/components/SearchInput";
import { PageListSkeleton } from "@/components/skeletons";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/dropdown-menu";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  getWorkflowSchedules,
  deleteWorkflowSchedule,
  updateWorkflowSchedule,
  runWorkflowScheduleNow,
} from "@/services/workflowSchedules";
import { getAgentConfigsList } from "@/services/api";
import { WorkflowSchedule } from "@/interfaces/workflow-schedule.interface";
import ScheduleFormDialog from "./ScheduleFormDialog";
import RunHistoryDialog from "./RunHistoryDialog";

const statusVariant = (
  status?: string | null
): "default" | "secondary" | "destructive" | "outline" | "success" => {
  switch (status) {
    case "completed":
      return "success";
    case "failed":
      return "destructive";
    case "running":
      return "default";
    default:
      return "secondary";
  }
};

interface SchedulingViewProps {
  // When set, the view is scoped to a single agent: the list is filtered to
  // that agent and new/edited schedules are locked to it.
  agentId?: string;
  // Optional back-navigation handler. When provided, a back button is rendered
  // before the page title.
  onBack?: () => void;
}

const SchedulingView: React.FC<SchedulingViewProps> = ({ agentId, onBack }) => {
  const [schedules, setSchedules] = useState<WorkflowSchedule[]>([]);
  const [agentNames, setAgentNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<WorkflowSchedule | null>(null);
  const [historyFor, setHistoryFor] = useState<WorkflowSchedule | null>(null);
  const [toDelete, setToDelete] = useState<WorkflowSchedule | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [scheduleData, agentRes] = await Promise.all([
        getWorkflowSchedules(),
        getAgentConfigsList(1, 100),
      ]);
      setSchedules(scheduleData);
      const names: Record<string, string> = {};
      agentRes.items.forEach((a) => {
        names[a.id] = a.name;
      });
      setAgentNames(names);
    } catch {
      toast.error("Failed to load schedules");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const filtered = useMemo(
    () =>
      schedules.filter(
        (s) =>
          (!agentId || s.agent_id === agentId) &&
          s.name.toLowerCase().includes(searchTerm.toLowerCase())
      ),
    [schedules, searchTerm, agentId]
  );

  const handleToggleActive = async (schedule: WorkflowSchedule) => {
    const next = !schedule.is_active;
    setSchedules((prev) =>
      prev.map((s) => (s.id === schedule.id ? { ...s, is_active: next } : s))
    );
    try {
      await updateWorkflowSchedule(schedule.id, { is_active: next });
    } catch {
      toast.error("Failed to update schedule");
      setSchedules((prev) =>
        prev.map((s) =>
          s.id === schedule.id ? { ...s, is_active: schedule.is_active } : s
        )
      );
    }
  };

  const handleRunNow = async (schedule: WorkflowSchedule) => {
    try {
      await runWorkflowScheduleNow(schedule.id);
      toast.success("Run queued");
    } catch {
      toast.error("Failed to trigger run");
    }
  };

  const handleDelete = async () => {
    if (!toDelete) return;
    try {
      setDeleting(true);
      await deleteWorkflowSchedule(toDelete.id);
      toast.success("Schedule deleted");
      setSchedules((prev) => prev.filter((s) => s.id !== toDelete.id));
    } catch {
      toast.error("Failed to delete schedule");
    } finally {
      setDeleting(false);
      setToDelete(null);
    }
  };

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };

  const openEdit = (schedule: WorkflowSchedule) => {
    setEditing(schedule);
    setFormOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-center gap-4">
          {onBack && (
            <Button
              variant="ghost"
              size="icon"
              onClick={onBack}
              className="shrink-0 rounded-full"
              aria-label="Back to AI Agents"
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
          )}
          <div className="min-w-0">
            <h2 className="text-3xl font-bold">Scheduling</h2>
            <p className="text-zinc-400 font-normal mt-1">
              Schedule recurring runs of this workflow
            </p>
          </div>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
          <SearchInput
            value={searchTerm}
            onChange={setSearchTerm}
            placeholder="Search schedules..."
            className="w-full sm:w-[200px]"
          />
          <Button
            className="flex w-full items-center justify-center gap-2 rounded-full sm:w-auto"
            onClick={openCreate}
          >
            <Plus className="h-4 w-4" />
            New Schedule
          </Button>
        </div>
      </div>

      <div className="rounded-md border bg-card shadow-sm overflow-hidden">
        {loading ? (
          <PageListSkeleton variant="rich" rows={4} bordered={false} />
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
            <div className="rounded-full bg-gray-100 p-4">
              <CalendarClock className="h-12 w-12 text-gray-400" />
            </div>
            <h3 className="font-medium text-lg">
              {searchTerm ? "No matching schedules" : "No schedules yet"}
            </h3>
            <p className="text-sm text-gray-500 max-w-sm px-4">
              {searchTerm
                ? "Try adjusting your search query."
                : "Create a schedule to run an agent's workflow automatically on a recurring basis."}
            </p>
            {!searchTerm && (
              <Button onClick={openCreate} className="rounded-full flex items-center gap-2">
                <Plus className="h-4 w-4" />
                New Schedule
              </Button>
            )}
          </div>
        ) : (
          <div className="divide-y">
            {filtered.map((schedule) => (
              <div
                key={schedule.id}
                className="flex items-center justify-between gap-3 p-4"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium truncate">{schedule.name}</span>
                    <Badge variant="outline" className="gap-1">
                      <CalendarClock className="h-3 w-3" />
                      {schedule.cron_schedule}
                    </Badge>
                    {schedule.last_run_status && (
                      <Badge variant={statusVariant(schedule.last_run_status)}>
                        {schedule.last_run_status}
                      </Badge>
                    )}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {agentNames[schedule.agent_id] || "Unknown agent"}
                    {schedule.last_run_at && (
                      <>
                        {" · "}Last run:{" "}
                        {new Date(schedule.last_run_at).toLocaleString()}
                      </>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Switch
                    checked={schedule.is_active}
                    onCheckedChange={() => handleToggleActive(schedule)}
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1"
                    onClick={() => handleRunNow(schedule)}
                  >
                    <Play className="h-3.5 w-3.5" />
                    Run now
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => setHistoryFor(schedule)}>
                        <History className="mr-2 h-4 w-4" />
                        Run history
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => openEdit(schedule)}>
                        <Pencil className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => setToDelete(schedule)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <ScheduleFormDialog
        isOpen={formOpen}
        onClose={() => setFormOpen(false)}
        onSaved={fetchData}
        schedule={editing}
        lockedAgentId={agentId}
      />

      <RunHistoryDialog
        isOpen={!!historyFor}
        onClose={() => setHistoryFor(null)}
        schedule={historyFor}
      />

      <ConfirmDialog
        isOpen={!!toDelete}
        onOpenChange={(open) => !open && setToDelete(null)}
        onConfirm={handleDelete}
        isInProgress={deleting}
        itemName={toDelete?.name || ""}
        description={`This will permanently delete the schedule "${toDelete?.name}".`}
      />
    </div>
  );
};

export default SchedulingView;