import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Copy, Link2Off } from "lucide-react";
import toast from "react-hot-toast";

import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { getWorkflowTriggersByAgent } from "@/services/workflowTriggers";
import { WebhookTriggerNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { WebhookTriggerDialog } from "../../nodeDialogs/WebhookTriggerDialog";
import { WEBHOOK_TRIGGER_NODE_TYPE } from "../../utils/entryNodes";

const WebhookTriggerNode: React.FC<NodeProps<WebhookTriggerNodeData>> = ({ id, data, selected }) => {
  const nodeDefinition = nodeRegistry.getNodeType(WEBHOOK_TRIGGER_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const { agentId } = useParams<{ agentId: string }>();

  // Read-only lookup (never provisions): the endpoint exists only once the
  // settings dialog has been opened for this node.
  const { data: triggers } = useQuery({
    queryKey: ["workflowTriggers", agentId],
    queryFn: () => getWorkflowTriggersByAgent(agentId as string),
    enabled: !!agentId,
    staleTime: 30_000,
  });
  const trigger = triggers?.find((t) => t.node_id === id);

  const onUpdate = (updatedData: WebhookTriggerNodeData) => {
    data.updateNodeData?.(id, { ...data, ...updatedData });
  };

  const copyUrl = () => {
    if (!trigger?.url) return;
    void navigator.clipboard.writeText(trigger.url);
    toast.success("Endpoint URL copied.");
  };

  const mappedCount = (data.fieldMappings ?? []).filter((m) => m.key && m.path).length;

  return (
    <div className="relative">
      {/* Copy-URL affordance in the slot where an input handle would sit — the
          trigger's only handle is the output on the right. */}
      {selected && trigger?.url && (
        <div className="absolute right-full top-1/2 z-30 -translate-y-1/2 pr-3 nodrag nopan pointer-events-auto">
          <Button
            size="sm"
            onClick={copyUrl}
            className="gap-1.5 rounded-full whitespace-nowrap shadow-md"
            title="Copy the endpoint URL"
          >
            <Copy className="h-3.5 w-3.5" />
            Copy URL
          </Button>
        </div>
      )}

      <BaseNodeContainer
        id={id}
        data={data}
        selected={selected}
        iconName={nodeDefinition.icon}
        title={data.name || nodeDefinition.label}
        subtitle={nodeDefinition.shortDescription}
        color={color}
        nodeType={WEBHOOK_TRIGGER_NODE_TYPE}
        onSettings={() => setIsEditDialogOpen(true)}
      >
        <div className="p-4 mx-0.5 mb-0.5 bg-card rounded-sm space-y-2 text-xs">
          {trigger ? (
            <>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="font-mono text-[10px]">
                  {trigger.method}
                </Badge>
                <Badge variant="secondary" className="text-[10px] uppercase">
                  {trigger.auth_mode}
                </Badge>
                {!trigger.is_active && (
                  <Badge variant="destructive" className="text-[10px]">
                    Disabled
                  </Badge>
                )}
              </div>
              <p className="truncate font-mono text-muted-foreground" title={trigger.url}>
                {trigger.url.replace(/^https?:\/\//, "")}
              </p>
            </>
          ) : (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Link2Off className="h-3.5 w-3.5" />
              <span>Endpoint not generated yet — open settings.</span>
            </div>
          )}
          <p className="text-muted-foreground">
            {data.messagePath ? `message ← ${data.messagePath}` : "No message mapped"}
            {mappedCount > 0 ? ` · ${mappedCount} field${mappedCount === 1 ? "" : "s"} mapped` : ""}
          </p>
        </div>
      </BaseNodeContainer>

      <WebhookTriggerDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={WEBHOOK_TRIGGER_NODE_TYPE}
      />
    </div>
  );
};

export default React.memo(WebhookTriggerNode);
