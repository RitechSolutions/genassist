import React, { useEffect, useMemo, useState } from "react";
import { toast } from "react-hot-toast";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import { getAgentConfigsList } from "@/services/api";
import {
  createWorkflowSchedule,
  updateWorkflowSchedule,
} from "@/services/workflowSchedules";
import { AgentListItem } from "@/interfaces/ai-agent.interface";
import {
  ThreadIdMode,
  WorkflowSchedule,
} from "@/interfaces/workflow-schedule.interface";

interface ScheduleFormDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
  schedule?: WorkflowSchedule | null;
}

// 5-field cron validation (mirrors KnowledgeBaseForm / ML pipeline).
const isValidCron = (cron: string): boolean => {
  const cronRegex =
    /^(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*$/;
  return cronRegex.test(cron.trim());
};

const ScheduleFormDialog: React.FC<ScheduleFormDialogProps> = ({
  isOpen,
  onClose,
  onSaved,
  schedule,
}) => {
  const isEdit = Boolean(schedule);

  const [agents, setAgents] = useState<AgentListItem[]>([]);
  const [name, setName] = useState("");
  const [agentId, setAgentId] = useState("");
  const [cron, setCron] = useState("0 0 * * *");
  const [isActive, setIsActive] = useState(true);
  const [threadIdMode, setThreadIdMode] = useState<ThreadIdMode>("per_run");
  const [fixedThreadId, setFixedThreadId] = useState("");
  const [message, setMessage] = useState("");
  const [extraInputJson, setExtraInputJson] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    getAgentConfigsList(1, 100)
      .then((res) => setAgents(res.items))
      .catch(() => toast.error("Failed to load agents"));
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    if (schedule) {
      const inputData = { ...(schedule.input_data || {}) } as Record<string, unknown>;
      const msg = typeof inputData.message === "string" ? inputData.message : "";
      delete inputData.message;
      delete inputData.thread_id;
      setName(schedule.name);
      setAgentId(schedule.agent_id);
      setCron(schedule.cron_schedule);
      setIsActive(schedule.is_active);
      setThreadIdMode(schedule.thread_id_mode);
      setFixedThreadId(schedule.fixed_thread_id || "");
      setMessage(msg);
      setExtraInputJson(
        Object.keys(inputData).length ? JSON.stringify(inputData, null, 2) : ""
      );
    } else {
      setName("");
      setAgentId("");
      setCron("0 0 * * *");
      setIsActive(true);
      setThreadIdMode("per_run");
      setFixedThreadId("");
      setMessage("");
      setExtraInputJson("");
    }
  }, [isOpen, schedule]);

  const cronValid = useMemo(() => isValidCron(cron), [cron]);

  const handleSubmit = async () => {
    if (!name.trim()) {
      toast.error("Name is required");
      return;
    }
    if (!agentId) {
      toast.error("Please select an agent");
      return;
    }
    if (!cronValid) {
      toast.error("Invalid cron expression");
      return;
    }

    let extra: Record<string, unknown> = {};
    if (extraInputJson.trim()) {
      try {
        const parsed = JSON.parse(extraInputJson);
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
          throw new Error("not an object");
        }
        extra = parsed as Record<string, unknown>;
      } catch {
        toast.error("Additional input must be a valid JSON object");
        return;
      }
    }

    const inputData: Record<string, unknown> = { message, ...extra };

    const payload = {
      name: name.trim(),
      agent_id: agentId,
      cron_schedule: cron.trim(),
      is_active: isActive,
      input_data: inputData,
      thread_id_mode: threadIdMode,
      fixed_thread_id: threadIdMode === "fixed" ? fixedThreadId || null : null,
    };

    try {
      setSubmitting(true);
      if (isEdit && schedule) {
        await updateWorkflowSchedule(schedule.id, payload);
        toast.success("Schedule updated");
      } else {
        await createWorkflowSchedule(payload);
        toast.success("Schedule created");
      }
      onSaved();
      onClose();
    } catch (e) {
      toast.error(
        isEdit ? "Failed to update schedule" : "Failed to create schedule"
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Schedule" : "New Schedule"}</DialogTitle>
          <DialogDescription>
            Run an agent's latest workflow on a recurring cron schedule.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label htmlFor="schedule-name">Name</Label>
            <Input
              id="schedule-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Nightly report run"
            />
          </div>

          <div className="space-y-1.5">
            <Label>Agent</Label>
            <Select value={agentId} onValueChange={setAgentId}>
              <SelectTrigger>
                <SelectValue placeholder="Select an agent" />
              </SelectTrigger>
              <SelectContent>
                {agents.map((a) => (
                  <SelectItem key={a.id} value={a.id}>
                    {a.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              The agent's current (latest) workflow version runs each time.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="schedule-cron">Schedule (cron)</Label>
            <Input
              id="schedule-cron"
              value={cron}
              onChange={(e) => setCron(e.target.value)}
              placeholder="0 0 * * *"
              className={!cronValid && cron ? "border-destructive" : ""}
            />
            <p className="text-xs text-muted-foreground">
              Format: minute hour day month weekday (e.g. <code>*/15 * * * *</code>).
            </p>
          </div>

          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <div className="text-sm font-medium">Active</div>
              <p className="text-xs text-muted-foreground">
                Enable automatic runs on this schedule.
              </p>
            </div>
            <Switch checked={isActive} onCheckedChange={setIsActive} />
          </div>

          <div className="space-y-1.5">
            <Label>Conversation thread</Label>
            <Select
              value={threadIdMode}
              onValueChange={(v) => setThreadIdMode(v as ThreadIdMode)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="per_run">New thread each run</SelectItem>
                <SelectItem value="fixed">
                  Fixed thread (share memory across runs)
                </SelectItem>
              </SelectContent>
            </Select>
            {threadIdMode === "fixed" && (
              <Input
                value={fixedThreadId}
                onChange={(e) => setFixedThreadId(e.target.value)}
                placeholder="Optional: leave blank to auto-generate on first run"
              />
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="schedule-message">Message</Label>
            <Textarea
              id="schedule-message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Input message passed to the workflow's input node"
              rows={3}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="schedule-extra">Additional input fields (JSON)</Label>
            <Textarea
              id="schedule-extra"
              value={extraInputJson}
              onChange={(e) => setExtraInputJson(e.target.value)}
              placeholder='{ "customer_id": "123" }'
              rows={3}
              className="font-mono text-xs"
            />
            <p className="text-xs text-muted-foreground">
              Optional extra input-node fields merged into the run payload.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Saving..." : isEdit ? "Save" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ScheduleFormDialog;