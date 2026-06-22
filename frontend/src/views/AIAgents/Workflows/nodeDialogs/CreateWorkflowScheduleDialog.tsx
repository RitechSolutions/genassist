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
import { getAgentConfigsList } from "@/services/api";
import { AgentListItem } from "@/interfaces/ai-agent.interface";

type CreateWorkflowScheduleDialogProps = BaseNodeDialogProps<
  CreateWorkflowScheduleNodeData,
  CreateWorkflowScheduleNodeData
>;

export const CreateWorkflowScheduleDialog: React.FC<
  CreateWorkflowScheduleDialogProps
> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "");
  const [scheduleName, setScheduleName] = useState(data.scheduleName || "");
  const [agentId, setAgentId] = useState(data.agentId || "");
  const [cronSchedule, setCronSchedule] = useState(
    data.cronSchedule || "0 0 * * *"
  );
  const [isActive, setIsActive] = useState(data.isActive ?? true);
  const [threadIdMode, setThreadIdMode] = useState<"per_run" | "fixed">(
    data.threadIdMode || "per_run"
  );
  const [fixedThreadId, setFixedThreadId] = useState(data.fixedThreadId || "");
  const [message, setMessage] = useState(data.message || "");
  const [inputData, setInputData] = useState(data.inputData || "");
  const [agents, setAgents] = useState<AgentListItem[]>([]);
  const { toast } = useToast();

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "");
      setScheduleName(data.scheduleName || "");
      setAgentId(data.agentId || "");
      setCronSchedule(data.cronSchedule || "0 0 * * *");
      setIsActive(data.isActive ?? true);
      setThreadIdMode(data.threadIdMode || "per_run");
      setFixedThreadId(data.fixedThreadId || "");
      setMessage(data.message || "");
      setInputData(data.inputData || "");

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

  const handleSave = () => {
    // Validate the optional additional-input JSON before saving.
    if (inputData.trim()) {
      try {
        const parsed = JSON.parse(inputData);
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
          throw new Error("not an object");
        }
      } catch {
        toast({
          title: "Invalid JSON",
          description: "Additional input fields must be a valid JSON object.",
          variant: "destructive",
        });
        return;
      }
    }

    onUpdate({
      ...data,
      name,
      scheduleName,
      agentId,
      cronSchedule,
      isActive,
      threadIdMode,
      fixedThreadId,
      message,
      inputData,
    });
    onClose();
  };

  const currentData = {
    ...data,
    name,
    scheduleName,
    agentId,
    cronSchedule,
    isActive,
    threadIdMode,
    fixedThreadId,
    message,
    inputData,
  };

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
      data={currentData}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Node Name</Label>
        <RichInput
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter the name of this node"
          className="w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="workflow">Workflow</Label>
        <Select value={agentId} onValueChange={setAgentId}>
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
        <p className="text-xs text-gray-500">
          The latest published version of this workflow runs on each scheduled
          execution.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="scheduleName">Schedule Name</Label>
        <RichInput
          id="scheduleName"
          value={scheduleName}
          onChange={(e) => setScheduleName(e.target.value)}
          placeholder="Name shown for the created schedule"
          className="w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="cron">Cron Schedule</Label>
        <RichInput
          id="cron"
          value={cronSchedule}
          onChange={(e) => setCronSchedule(e.target.value)}
          placeholder="0 0 * * *"
          className="w-full"
        />
        <p className="text-xs text-gray-500">
          Format: minute hour day month weekday (e.g. */15 * * * *).
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="message">Message</Label>
        <DraggableTextArea
          id="message"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Message passed to the workflow's input node on each run"
          className="w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="inputData">Additional input fields (JSON)</Label>
        <DraggableTextArea
          id="inputData"
          value={inputData}
          onChange={(e) => setInputData(e.target.value)}
          placeholder='{ "customer_id": "123" }'
          className="w-full font-mono text-xs"
        />
        <p className="text-xs text-gray-500">
          Optional extra input-node fields merged into each run's payload.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="threadIdMode">Conversation Thread</Label>
        <Select
          value={threadIdMode}
          onValueChange={(v) => setThreadIdMode(v as "per_run" | "fixed")}
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

      {threadIdMode === "fixed" && (
        <div className="space-y-2">
          <Label htmlFor="fixedThreadId">Fixed Thread ID</Label>
          <RichInput
            id="fixedThreadId"
            value={fixedThreadId}
            onChange={(e) => setFixedThreadId(e.target.value)}
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
            checked={isActive}
            onCheckedChange={(checked) => setIsActive(checked as boolean)}
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
