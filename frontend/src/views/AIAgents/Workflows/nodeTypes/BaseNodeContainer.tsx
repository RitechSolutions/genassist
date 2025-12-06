import React, { useState } from "react";
import { NodeData } from "../types/nodes";
import { useReactFlow } from "reactflow";
import { HandlersRenderer } from "../components/custom/HandleTooltip";
import { GenericTestDialog } from "../components/GenericTestDialog";
import NodeHeader from "./nodeHeader";
import { NODE_WIDTH } from "./nodeConstants";
import { useWorkflowExecution } from "../context/WorkflowExecutionContext";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import nodeRegistry from "../registry/nodeRegistry";
import { useNodeValidation } from "../hooks/useNodeValidation";

interface BaseNodeContainerProps<T extends NodeData> {
  id: string;
  data: T;
  selected: boolean;
  iconName: string;
  title: string;
  subtitle: string;
  color: string;
  nodeType: string;
  onSettings?: () => void;
  children: React.ReactNode;
}

const BaseNodeContainer = <T extends NodeData>({
  id,
  data,
  selected,
  iconName,
  title,
  subtitle,
  color,
  nodeType,
  onSettings,
  children,
}: BaseNodeContainerProps<T>) => {
  const nodeDefinition = nodeRegistry.getNodeType(nodeType);

  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const { hasNodeBeenExecuted, updateNodeOutput } = useWorkflowExecution();
  const { deleteElements } = useReactFlow();
  const { hasValidationError } = useNodeValidation(nodeType, data);

  const handleTest = () => {
    setIsTestDialogOpen(true);
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    deleteElements({ nodes: [{ id }] });
    setIsDeleting(false);
  };

  // Determine border color based on execution status
  const getBorderColor = () => {
    if (selected) return "border-blue-500";
    if (!hasNodeBeenExecuted(id) || hasValidationError) return "border-red-300";
    return "border-gray-200";
  };

  const nodeName = data.name || nodeDefinition?.label || "node";

  return (
    <>
      <div
        className={`border-2 rounded-md shadow-md ${NODE_WIDTH} ${getBorderColor()}`}
        style={{ backgroundColor: "#F4F4F5" }}
      >
        {/* Node header */}
        <NodeHeader
          iconName={iconName}
          title={title}
          subtitle={subtitle}
          color={color}
          onSettings={onSettings}
          onTest={handleTest}
          onDeleteClick={() => setIsDeleteDialogOpen(true)}
        />

        {/* Node content - passed as children */}
        {children}

        {/* Handlers */}
        <HandlersRenderer id={id} data={data} />
      </div>

      {/* Generic Test Dialog - automatically included */}
      <GenericTestDialog
        isOpen={isTestDialogOpen}
        onClose={() => setIsTestDialogOpen(false)}
        nodeType={nodeType}
        nodeData={data}
        nodeId={id}
        nodeName={nodeName}
      />

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDelete}
        isInProgress={isDeleting}
        itemName={title}
      ></ConfirmDialog>
    </>
  );
};

export default BaseNodeContainer;
