import React, { useEffect, useState } from "react";
import { toast } from "react-hot-toast";

import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { JsonInput } from "@/components/JsonInput";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import { CRUDDialog } from "@/components/ui/crud-dialog";
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
  // When set, the schedule is locked to this agent and the workflow selector
  // is hidden (the dialog is opened from that agent's Scheduling page).
  lockedAgentId?: string;
}

type ScheduleFormValues = {
  name: string;
  agentId: string;
  cron: string;
  isActive: boolean;
  threadIdMode: ThreadIdMode;
  fixedThreadId: string;
  message: string;
  extraInputJson: string;
};

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
  lockedAgentId,
}) => {
  const isEdit = Boolean(schedule);

  const [agents, setAgents] = useState<AgentListItem[]>([]);
  const [extraInputValid, setExtraInputValid] = useState(true);

  useEffect(() => {
    if (!isOpen) return;
    getAgentConfigsList(1, 100)
      .then((res) => setAgents(res.items))
      .catch(() => toast.error("Failed to load agents"));
  }, [isOpen]);

  return (
    <CRUDDialog<ScheduleFormValues>
      open={isOpen}
      onOpenChange={(open) => !open && onClose()}
      mode={isEdit ? "edit" : "create"}
      maxWidth="512px"
      resetKey={schedule?.id ?? null}
      initialValues={{
        name: "",
        agentId: lockedAgentId || "",
        cron: "0 0 * * *",
        isActive: true,
        threadIdMode: "per_run",
        fixedThreadId: "",
        message: "",
        extraInputJson: "",
      }}
      editValues={
        schedule
          ? (() => {
              const inputData = {
                ...(schedule.input_data || {}),
              } as Record<string, unknown>;
              const msg =
                typeof inputData.message === "string" ? inputData.message : "";
              delete inputData.message;
              delete inputData.thread_id;
              return {
                name: schedule.name,
                agentId: schedule.agent_id,
                cron: schedule.cron_schedule,
                isActive: schedule.is_active,
                threadIdMode: schedule.thread_id_mode,
                fixedThreadId: schedule.fixed_thread_id || "",
                message: msg,
                extraInputJson: Object.keys(inputData).length
                  ? JSON.stringify(inputData, null, 2)
                  : "",
              };
            })()
          : null
      }
      title={{ create: "New Schedule", edit: "Edit Schedule" }}
      description="Run an agent's latest workflow on a recurring cron schedule."
      submitLabel={{ create: "Create", edit: "Save" }}
      loadingLabel="Saving..."
      successMessage={{ create: "Schedule created", edit: "Schedule updated" }}
      errorMessage={(_err, m) =>
        m === "create" ? "Failed to create schedule" : "Failed to update schedule"
      }
      validate={(values) => {
        if (!values.name.trim()) {
          toast.error("Name is required");
          return { name: "invalid" };
        }
        if (!values.agentId) {
          toast.error("Please select an agent");
          return { agentId: "invalid" };
        }
        if (!isValidCron(values.cron)) {
          toast.error("Invalid cron expression");
          return { cron: "invalid" };
        }
        if (values.extraInputJson.trim()) {
          if (!extraInputValid) {
            toast.error("Additional input fields must be valid JSON");
            return { extraInputJson: "invalid" };
          }
          const parsed = JSON.parse(values.extraInputJson);
          if (
            typeof parsed !== "object" ||
            parsed === null ||
            Array.isArray(parsed)
          ) {
            toast.error("Additional input fields must be a JSON object");
            return { extraInputJson: "invalid" };
          }
        }
        return null;
      }}
      onSubmit={async (values, { mode: m }) => {
        let extra: Record<string, unknown> = {};
        if (values.extraInputJson.trim()) {
          extra = JSON.parse(values.extraInputJson) as Record<string, unknown>;
        }

        const inputData: Record<string, unknown> = { message: values.message, ...extra };

        const payload = {
          name: values.name.trim(),
          agent_id: values.agentId,
          cron_schedule: values.cron.trim(),
          is_active: values.isActive,
          input_data: inputData,
          thread_id_mode: values.threadIdMode,
          fixed_thread_id:
            values.threadIdMode === "fixed" ? values.fixedThreadId || null : null,
        };

        if (m === "edit" && schedule) {
          await updateWorkflowSchedule(schedule.id, payload);
        } else {
          await createWorkflowSchedule(payload);
        }
        onSaved();
      }}
    >
      {({ values, setField }) => {
        const cronValid = isValidCron(values.cron);
        return (
          <>
            <div className="space-y-1.5">
              <Label htmlFor="schedule-name">Name</Label>
              <Input
                id="schedule-name"
                value={values.name}
                onChange={(e) => setField("name", e.target.value)}
                placeholder="Nightly report run"
              />
            </div>

            {!lockedAgentId && (
              <div className="space-y-1.5">
                <Label>Workflow</Label>
                <Select
                  value={values.agentId}
                  onValueChange={(v) => setField("agentId", v)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a workflow" />
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
                  The latest published version of this workflow runs each time.
                </p>
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="schedule-cron">Schedule (cron)</Label>
              <Input
                id="schedule-cron"
                value={values.cron}
                onChange={(e) => setField("cron", e.target.value)}
                placeholder="0 0 * * *"
                className={!cronValid && values.cron ? "border-destructive" : ""}
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
              <Switch
                checked={values.isActive}
                onCheckedChange={(checked) => setField("isActive", checked)}
              />
            </div>

            <div className="space-y-1.5">
              <Label>Conversation thread</Label>
              <Select
                value={values.threadIdMode}
                onValueChange={(v) => setField("threadIdMode", v as ThreadIdMode)}
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
              {values.threadIdMode === "fixed" && (
                <Input
                  value={values.fixedThreadId}
                  onChange={(e) => setField("fixedThreadId", e.target.value)}
                  placeholder="Optional: leave blank to auto-generate on first run"
                />
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="schedule-message">Message</Label>
              <Textarea
                id="schedule-message"
                value={values.message}
                onChange={(e) => setField("message", e.target.value)}
                placeholder="Input message passed to the workflow's input node"
                size="body"
              />
            </div>

            <div className="space-y-1.5">
              <JsonInput
                value={values.extraInputJson}
                onChange={(v) => setField("extraInputJson", v)}
                onValidChange={(valid) => setExtraInputValid(valid)}
                label="Additional input fields (JSON)"
                description="Optional extra input-node fields merged into the run payload."
                placeholder='{ "customer_id": "123" }'
                rows={8}
                allowEmpty
              />
            </div>
          </>
        );
      }}
    </CRUDDialog>
  );
};

export default ScheduleFormDialog;
