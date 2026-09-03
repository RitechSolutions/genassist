import React, { useState, useEffect } from "react";
import { CreateWorkflowScheduleNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import { Checkbox } from "@/components/checkbox";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import { useToast } from "@/components/use-toast";
import { Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import { DraggableInput } from "../components/custom/DraggableInput";
import { getAgentConfigsList } from "@/services/api";
import { AgentListItem } from "@/interfaces/ai-agent.interface";
import { useNodeDialogState } from "./useNodeDialogState";

type CreateWorkflowScheduleDialogProps = BaseNodeDialogProps<
  CreateWorkflowScheduleNodeData,
  CreateWorkflowScheduleNodeData
>;

export const CreateWorkflowScheduleDialog: React.FC<
  CreateWorkflowScheduleDialogProps
> = (props) => {
  const { isOpen, onClose, data } = props;

  // Note: we intentionally do NOT hard-validate the additional-input JSON on
  // save. The field supports dropped source variables (e.g. {{source.id}}),
  // which aren't valid JSON at design time; the backend resolves templates
  // first and then parses leniently, ignoring anything it can't read.
  const { values, setField, merged, handleSave } = useNodeDialogState(
    props,
    () => ({
      name: data.name || "",
      scheduleName: data.scheduleName || "",
      agentId: data.agentId || "",
      cronSchedule: data.cronSchedule || "0 0 * * *",
      isActive: data.isActive ?? true,
      threadIdMode: (data.threadIdMode || "per_run") as "per_run" | "fixed",
      fixedThreadId: data.fixedThreadId || "",
      message: data.message || "",
      inputData: data.inputData || "",
    })
  );

  const [agents, setAgents] = useState<AgentListItem[]>([]);
  const { toast } = useToast();

  useEffect(() => {
    if (isOpen) {
      const loadAgents = async () => {
        try {
          const res = await getAgentConfigsList(1, 100);
          setAgents(res.items);
        } catch {
          toast({
            title: "Error",
            description: "Failed to load workflows",
            variant: "destructive",
          });
        }
      };
      loadAgents();
    }
  }, [isOpen, data, toast]);

  return (
    <NodeConfigPanel
      isOpen={isOpen}
      onClose={onClose}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </>
      }
      {...props}
      data={merged}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Node Name</Label>
        <RichInput
          id="name"
          value={values.name}
          onChange={(e) => setField("name", e.target.value)}
          placeholder="Enter the name of this node"
          className="w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="workflow">Workflow</Label>
        <Select
          value={values.agentId}
          onValueChange={(value) => setField("agentId", value)}
        >
          <SelectTrigger id="workflow">
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
          The latest published version of this workflow runs on each scheduled
          execution.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="scheduleName">Schedule Name</Label>
        <DraggableInput
          id="scheduleName"
          value={values.scheduleName}
          onChange={(e) => setField("scheduleName", e.target.value)}
          placeholder="Name shown for the created schedule"
          className="w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="cron">Cron Schedule</Label>
        <DraggableInput
          id="cron"
          value={values.cronSchedule}
          onChange={(e) => setField("cronSchedule", e.target.value)}
          placeholder="0 0 * * *"
          className="w-full"
        />
        <p className="text-xs text-muted-foreground">
          Format: minute hour day month weekday (e.g. */15 * * * *).
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="message">Message</Label>
        <DraggableTextArea
          id="message"
          size="body"
          value={values.message}
          onChange={(e) => setField("message", e.target.value)}
          placeholder="Message passed to the workflow's input node on each run"
          className="w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="inputData">Additional input fields (JSON)</Label>
        <DraggableTextArea
          id="inputData"
          size="code"
          value={values.inputData}
          onChange={(e) => setField("inputData", e.target.value)}
          placeholder='{ "customer_id": "123" }'
          className="w-full font-mono text-xs"
        />
        <p className="text-xs text-muted-foreground">
          Optional extra input-node fields merged into each run's payload.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="threadIdMode">Conversation Thread</Label>
        <Select
          value={values.threadIdMode}
          onValueChange={(v) =>
            setField("threadIdMode", v as "per_run" | "fixed")
          }
        >
          <SelectTrigger id="threadIdMode">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="per_run">New thread each run</SelectItem>
            <SelectItem value="fixed">
              Fixed thread (share memory across runs)
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      {values.threadIdMode === "fixed" && (
        <div className="space-y-2">
          <Label htmlFor="fixedThreadId">Fixed Thread ID</Label>
          <DraggableInput
            id="fixedThreadId"
            value={values.fixedThreadId}
            onChange={(e) => setField("fixedThreadId", e.target.value)}
            placeholder="Leave blank to auto-generate on first run"
            className="w-full"
          />
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="isActive">Status</Label>
        <div className="flex items-center space-x-2 h-10">
          <Checkbox
            id="isActive"
            checked={values.isActive}
            onCheckedChange={(checked) =>
              setField("isActive", checked as boolean)
            }
          />
          <Label
            htmlFor="isActive"
            className="text-sm font-normal cursor-pointer"
          >
            Enable automatic runs
          </Label>
        </div>
      </div>
    </NodeConfigPanel>
  );
};
