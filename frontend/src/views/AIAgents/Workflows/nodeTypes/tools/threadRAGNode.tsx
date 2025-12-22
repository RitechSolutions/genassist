import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { ThreadRAGNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { ThreadRAGDialog } from "../../nodeDialogs/ThreadRAGDialog";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const THREAD_RAG_NODE_TYPE = "threadRAGNode";

const ThreadRAGNode: React.FC<NodeProps<ThreadRAGNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(THREAD_RAG_NODE_TYPE);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const color = getNodeColor(nodeDefinition.category);

  const onUpdate = (updatedData: ThreadRAGNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<ThreadRAGNodeData> = {
        ...data,
        ...updatedData,
      };
      data.updateNodeData(id, dataToUpdate);
    }
  };

  const limit = data.top_k ? data.top_k : 0;

  // Prepare display content based on action
  const getNodeContent = () => {
    const nodeContent: NodeContentRow[] = [
      { label: "Action", value: data.action, isSelection: true },
    ];
    if (data.action === "retrieve") {
      nodeContent.push(
        { label: "Query", value: data.query },
        {
          label: "Limit",
          value:
            limit === 0
              ? ""
              : limit === 1
              ? `Top result`
              : `Top ${limit} results`,
        }
      );
    } else {
      nodeContent.push({ label: "Message", value: data.message });
    }
    return nodeContent;
  };

  return (
    <>
      <BaseNodeContainer
        id={id}
        data={data}
        selected={selected}
        iconName="database"
        title={data.name || "Thread RAG"}
        subtitle={
          data.action === "retrieve"
            ? "Retrieve context from chat RAG"
            : "Add message to chat RAG"
        }
        color={color}
        nodeType={THREAD_RAG_NODE_TYPE}
        nodeContent={getNodeContent()}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      {/* Edit Dialog */}
      <ThreadRAGDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={THREAD_RAG_NODE_TYPE}
      />
    </>
  );
};

export default ThreadRAGNode;
