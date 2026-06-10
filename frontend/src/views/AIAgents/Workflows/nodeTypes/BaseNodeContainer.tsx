import { useState } from "react";
import { NodeData, NodeHelpContent } from "../types/nodes";
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
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { getNodeBgColor, getNodeIconColor } from "../utils/nodeColors";
import { renderIcon } from "../utils/iconUtils";
import {
  defaultHelpHeaderGradient,
  helpHeaderGradientByCategory,
} from "../utils/helpHeaderGradients";

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
  const [isHelpDialogOpen, setIsHelpDialogOpen] = useState(false);
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
  const isAgentNode = nodeType === "agentNode";

  const cardColor = hasError
    ? "red-200"
    : isSpecialNode
    ? "brand-600"
    : `${color.split("-")[0]}-50`;
  const iconColor = hasError ? "red-600" : isSpecialNode ? "white" : color;
  const icon = hasError ? "CircleAlert" : iconName;
  const nodeCategory = nodeDefinition?.category ?? "utils";
  const categoryLabel: Record<string, string> = {
    io: "I/O",
    ai: "AI",
    routing: "Routing",
    integrations: "Integrations",
    formatting: "Formatting",
    tools: "Tools",
    training: "Training",
    utils: "Utils",
  };
  const helpContent: NodeHelpContent = nodeDefinition?.helpContent ?? {
    intro: nodeDefinition?.description ?? subtitle,
    sections: nodeDefinition?.shortDescription
      ? [{ title: "Quick Overview", body: nodeDefinition.shortDescription }]
      : [],
  };

  const renderHelpContent = (content: NodeHelpContent) => (
    <div className="space-y-8">
      <DialogDescription className="text-[18px] leading-8 text-foreground">
        {content.intro}
      </DialogDescription>
      {content.sections?.map((section) => (
        <section key={section.title} className="space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            {section.title}
          </h3>
          {section.body && (
            <p className="text-base leading-7 text-foreground">{section.body}</p>
          )}
          {section.bullets && section.bullets.length > 0 && (
            <ul className="space-y-2 pl-5 text-base leading-7 text-foreground list-disc">
              {section.bullets.map((bullet) => (
                <li key={bullet}>{bullet}</li>
              ))}
            </ul>
          )}
          {section.steps && section.steps.length > 0 && (
            <ol className="space-y-2 pl-5 text-base leading-7 text-foreground list-decimal">
              {section.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          )}
        </section>
      ))}
    </div>
  );

  const card = (
    <div
      className={`rounded-[6px] bg-${cardColor} ${NODE_WIDTH} self-stretch ${isAgentNode ? "" : `border-2 ${getBorderColor()}`}`}
      style={{
        boxShadow: isAgentNode ? undefined : "0 0 10px rgba(0, 0, 0, 0.2)",
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
        onHelpClick={() => setIsHelpDialogOpen(true)}
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
  );

  return (
    <>
      {isAgentNode ? (
        <div
          className={`agent-gradient-border${selected ? " ring-2 ring-blue-500 ring-offset-1" : ""}`}
          style={{ boxShadow: "0 0 16px rgba(192, 132, 252, 0.4)" }}
        >
          {card}
        </div>
      ) : (
        card
      )}

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
      />

      <Dialog open={isHelpDialogOpen} onOpenChange={setIsHelpDialogOpen}>
        <DialogContent className="w-[min(92vw,860px)] max-w-[860px] min-h-[420px] max-h-[90vh] p-0 overflow-hidden rounded-xl border border-gray-200 shadow-2xl">
          <div className="flex min-h-[420px] max-h-[90vh] flex-col bg-white">
            <div
              className={`px-10 pt-10 pb-6 ${
                helpHeaderGradientByCategory[nodeCategory] ??
                defaultHelpHeaderGradient
              }`}
            >
              <div className="flex items-start gap-4">
                <div
                  className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ${getNodeBgColor(
                    nodeCategory
                  )}`}
                >
                  {renderIcon(
                    nodeDefinition?.icon ?? iconName,
                    `h-5 w-5 ${getNodeIconColor(nodeCategory)}`
                  )}
                </div>
                <DialogHeader className="m-0 flex-1 space-y-3 text-left">
                  <div className="flex items-center gap-3">
                    <DialogTitle className="text-[32px] font-semibold leading-tight text-foreground">
                      {nodeDefinition?.label ?? title} Help
                    </DialogTitle>
                    <Badge
                      variant="secondary"
                      className="rounded-md px-2.5 py-1 text-[11px] uppercase tracking-[0.14em]"
                    >
                      {categoryLabel[nodeCategory] ?? nodeCategory}
                    </Badge>
                  </div>
                </DialogHeader>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-10 pb-8 pt-8">
              {renderHelpContent(helpContent)}
            </div>
            <div className="flex justify-end px-10 pb-10">
              <DialogClose asChild>
                <Button
                  type="button"
                  variant="secondary"
                  className="h-11 rounded-full px-7 text-base font-medium shadow-sm"
                >
                  Close
                </Button>
              </DialogClose>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default BaseNodeContainer;
