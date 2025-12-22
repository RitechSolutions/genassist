import { useState } from "react";
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
import { NodeContent, NodeContentRow } from "./nodeContent";
import { NodeAlert } from "./nodeAlert";

interface BaseNodeContainerProps<T extends NodeData> {
  id: string;
  data: T;
  selected: boolean;
  iconName: string;
  title: string;
  subtitle: string;
  color: string;
  nodeType: string;
  nodeContent?: NodeContentRow[];
  onSettings?: () => void;
  children?: React.ReactNode;
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
  nodeContent,
  onSettings,
  children,
}: BaseNodeContainerProps<T>) => {
  const nodeDefinition = nodeRegistry.getNodeType(nodeType);

  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const { hasNodeBeenExecuted, updateNodeOutput } = useWorkflowExecution();
  const { deleteElements } = useReactFlow();
  const { hasValidationError, missingFields } = useNodeValidation(
    nodeType,
    data
  );

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
    return "border-transparent";
  };

  const nodeName = data.name || nodeDefinition?.label || "node";

  const hasError = !hasNodeBeenExecuted(id) || hasValidationError;
  const isSpecialNode =
    nodeType === "chatInputNode" || nodeType === "chatOutputNode";

  const cardColor = hasError
    ? "red-200"
    : isSpecialNode
    ? "brand-600"
    : `${color.split("-")[0]}-50`;
  const iconColor = hasError ? "red-600" : isSpecialNode ? "white" : color;
  const icon = hasError ? "CircleAlert" : iconName;

  return (
    <>
      <div
        className={`border-2 rounded-md bg-${cardColor} ${NODE_WIDTH} ${getBorderColor()}`}
        style={{
          boxShadow: "0 0 10px rgba(0, 0, 0, 0.2)",
        }}
      >
        {/* Node header */}
        <NodeHeader
          iconName={icon}
          title={title}
          subtitle={subtitle}
          color={iconColor}
          hasError={hasError}
          isSpecialNode={isSpecialNode}
          onSettings={onSettings}
          onTest={handleTest}
          onDeleteClick={() => setIsDeleteDialogOpen(true)}
        />

        {/* Node content */}
        {nodeContent && <NodeContent data={nodeContent} />}
        {children}

        {/* Handlers */}
        <HandlersRenderer id={id} data={data} />

        {hasError && (
          <NodeAlert
            missingFields={missingFields}
            onFix={onSettings}
            onTest={handleTest}
          />
        )}
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
