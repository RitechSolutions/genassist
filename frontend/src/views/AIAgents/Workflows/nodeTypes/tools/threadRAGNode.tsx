import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { ThreadRAGNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import { ThreadRAGDialog } from "../../nodeDialogs/ThreadRAGDialog";
import nodeRegistry from "../../registry/nodeRegistry";

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

  // Prepare display content based on action
  const getDisplayContent = () => {
    if (data.action === "retrieve") {
      return [
        {
          label: "Action",
          value: data.action,
        },
        {
          label: "Query",
          value: data.query,
        },
        {
          label: "Top K",
          value: data.top_k?.toString(),
        },
      ];
    } else {
      return [
        {
          label: "Action",
          value: "Add Message to RAG",
        },
        {
          label: "Message",
          value: data.message || "",
          placeholder: "No message provided",
        },
      ];
    }
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
        onSettings={() => setIsEditDialogOpen(true)}
        testTitle={`Test ${data.name || "Thread RAG"}`}
        testDescription={
          data.action === "retrieve"
            ? "Test retrieving context from the thread RAG"
            : "Test adding a message to the thread RAG"
        }
      >
        <NodeContent data={getDisplayContent()} />
      </BaseNodeContainer>

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
