import React, { useEffect, useState } from "react";
import { Handle, Position, NodeProps } from "reactflow";
import { Save, Play, MessageCircle } from "lucide-react";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { HandleTooltip } from "../../components/HandleTooltip";
import { TestDialog, TestInputField } from "../../components/TestDialog";
import { createSimpleSchema } from "../../types/schemas";
import { getNodeColors } from "../../utils/nodeColors";
import { SlackOutputNodeData } from "../../types/nodes";
import {slackMessageOutput} from "@/services/workflows"
const SlackOutputNode: React.FC<NodeProps<SlackOutputNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const colors = getNodeColors("slackMessageNode");

  const [name, setLabel] = useState(data.name || "Slack Message");
  const [token, setToken] = useState(data.token || "");
  const [channel, setChannel] = useState(data.channel || "");
  const [response, setResponse] = useState<string>("");
  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    saveConfiguration();
  }, [name, token, channel]);

  const saveConfiguration = () => {
    const inputSchema = createSimpleSchema({
      text: { type: "string", required: true },
    });

    const outputSchema = createSimpleSchema({
      status: { type: "number", required: true },
      data: { type: "any", required: true },
    });

    if (data.updateNodeData) {
      data.updateNodeData(id, {
        ...data,
        token,
        channel,
        inputSchema,
        outputSchema,
      });
    }
  };

  const executeSlackMessage = async (inputs: Record<string, string>) => {
    try {
        setIsLoading(true);
        setError(null);
        const message = inputs.text;

        const result = await slackMessageOutput(message, {
        token,
        channel,
        name,
        handlers: data.handlers,
        });

        setResponse(JSON.stringify(result, null, 2));
    } catch (err) {
        const errorMessage =
        err instanceof Error ? err.message : "Unknown error occurred";
        setError(errorMessage);
        setResponse(`Error: ${errorMessage}`);
    } finally {
        setIsLoading(false);
    }
  };


  return (
    <>
      <div
        className={`border-2 rounded-md bg-white shadow-md w-[400px] ${
          selected ? "border-blue-500" : "border-gray-200"
        }`}
      >
        {/* Header */}
        <div className={`px-4 py-2 border-b ${colors.header} flex justify-between items-center`}>
          <div className="flex items-center">
            <MessageCircle className="h-4 w-4 text-white mr-2" />
             <div className="text-sm font-medium text-white">Slack Message Output</div>
          </div>
          <div className="flex space-x-1">
            <Button
              size="icon"
              variant="ghost"
              className={`h-6 w-6 text-white ${colors.hover}`}
              title="Test Slack message"
              onClick={() => setIsTestDialogOpen(true)}
            >
              <Play className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* Body */}
        <div className="p-4 space-y-4">
          <div className="space-y-2">
            <Label htmlFor="token">Slack Bot Token</Label>
            <Input
              id="token"
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="xoxb-..."
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="channel">Slack Channel ID</Label>
            <Input
              id="channel"
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
              placeholder="C12345678 / U12345678 or email"
            />
          </div>
        </div>

        {/* Handles */}
        {data.handlers?.map((handler, index) => (
          <HandleTooltip
            key={handler.id}
            type={handler.type}
            position={handler.type === "source" ? Position.Right : Position.Left}
            id={handler.id}
            nodeId={id}
            compatibility={handler.compatibility}
            style={{ top: `${(index + 1) * (100 / data.handlers.length)}%` }}
          />
        ))}
      </div>

      <TestDialog
        isOpen={isTestDialogOpen}
        onClose={() => setIsTestDialogOpen(false)}
        title={`Test Slack Message: ${name}`}
        description="Send a test message to the configured Slack channel."
        inputFields={[{ id: "text", label: "Message", type: "string", required: true }]}
        onRun={executeSlackMessage}
        output={response}
        isLoading={isLoading}
        error={error}
      />
    </>
  );
};

export default SlackOutputNode;
