import { useContext, useEffect, useRef, useState } from "react";
import { NodeData, NodeHelpContent } from "../types/nodes";
import { useReactFlow } from "reactflow";
import { WorkflowContext } from "../context/WorkflowContext";
import { DEFAULT_NODE_STYLE } from "@/interfaces/workflow.interface";
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
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/RadixTooltip";
import { getNodeBgColor, getNodeIconColor } from "../utils/nodeColors";
import { renderIcon } from "../utils/iconUtils";
import {
  defaultHelpHeaderGradient,
  helpHeaderGradientByCategory,
} from "../utils/helpHeaderGradients";
import { getNodeDocsUrl } from "../utils/nodeDocsLinks";
import {
  CircleAlert,
  ExternalLink,
  MoreVertical,
  Play,
  Settings,
  Trash2,
} from "lucide-react";
import NodeActionsMenu from "../components/NodeActionsMenu";
import RenameNodeDialog from "../components/RenameNodeDialog";
import { useNodeActions } from "../context/NodeActionsContext";

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

  // Read the per-workflow node rendering style. Read the context directly
  // (not the throwing `useWorkflow` hook) so nodes still render in the
  // read-only Execution/Diff views, which mount them without a WorkflowProvider
  // — there we simply fall back to the default "detailed" style.
  const workflowCtx = useContext(WorkflowContext);
  const nodeStyle =
    workflowCtx?.workflow?.settings?.nodeStyle ?? DEFAULT_NODE_STYLE;
  const isCompact = nodeStyle === "compact";

  const handleTest = () => {
    setIsTestDialogOpen(true);
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    deleteElements({ nodes: [{ id }] });
    setIsDeleting(false);
  };

  // A deactivated node is bypassed at execution time (the engine forwards the
  // upstream output straight to the next node). The flag lives on the node's
  // `data` and is persisted with the workflow (workflows.nodes JSONB).
  const isDeactivated = !!data.deactivated;
  const handleToggleActive = () => {
    data.updateNodeData?.(id, { deactivated: !isDeactivated });
  };

  // Canvas-level per-node actions (duplicate/copy/replace) provided by GraphFlow.
  const nodeActions = useNodeActions();
  const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);
  const handleRename = (newName: string) =>
    data.updateNodeData?.(id, { name: newName });

  // Shared props for the 3-dots actions menu (used by both node views).
  // `canModify` is set below once isSpecialNode is known.
  const nodeMenuHandlers = {
    deactivated: isDeactivated,
    onConfigure: onSettings,
    onRename: () => setIsRenameDialogOpen(true),
    onReplace: () => nodeActions?.requestReplaceNode(id),
    onToggleActive: handleToggleActive,
    onCopy: () => nodeActions?.copyNode(id),
    onDuplicate: () => nodeActions?.duplicateNode(id),
    onHelp: () => setIsHelpDialogOpen(true),
    onDelete: () => setIsDeleteDialogOpen(true),
  };

  // Determine border color based on execution status
  const getBorderColor = () => {
    if (selected) return "border-blue-500";
    return "border-transparent";
  };

  const nodeName = data.name || nodeDefinition?.label || "node";

  // A deactivated node won't run, so it should not surface "not executed" /
  // validation errors — it renders in a calm, dimmed state instead.
  const hasError = isDeactivated
    ? false
    : !hasNodeBeenExecuted(id) || hasValidationError;
  const isSpecialNode =
    nodeType === "chatInputNode" || nodeType === "chatOutputNode";
  // Sub-agents share the agent's gradient treatment
  const isAgentNode =
    nodeType === "agentNode" || nodeType === "subAgentNode";
  // The agent node's distinctive animated gradient border is dropped while
  // deactivated, so a bypassed agent looks like every other deactivated node.
  const showAgentStyle = isAgentNode && !isDeactivated;
  // Actions that don't apply to the special I/O nodes (Start/Output).
  const canModify = !isSpecialNode;

  // Keyboard shortcuts for the selected node — mirror the 3-dots actions menu.
  // Rebuilt each render (captures the latest handlers) and invoked through a ref,
  // so the listener effect only re-registers when selection changes. Copy (⌘C)
  // and Delete (⌫) are already handled globally, so they're not repeated here.
  const nodeShortcutRef = useRef<(e: KeyboardEvent) => void>();
  nodeShortcutRef.current = (e: KeyboardEvent) => {
    const target = e.target as HTMLElement;
    // Ignore while typing, or while a dialog/menu is the active surface.
    if (
      target.isContentEditable ||
      target.closest(
        "input, textarea, select, button, [contenteditable='true'], .ace_editor, [role='dialog'], [role='menu']"
      )
    ) {
      return;
    }
    // Only act when THIS node is the sole selection; when several are selected
    // every listener bails so nothing ambiguous fires.
    if (
      document.querySelectorAll(".react-flow__node.selected").length !== 1
    ) {
      return;
    }

    const meta = e.metaKey || e.ctrlKey;
    // ⌘/Ctrl+D → Duplicate.
    if (meta && e.key.toLowerCase() === "d") {
      if (!canModify) return;
      e.preventDefault();
      nodeActions?.duplicateNode(id);
      return;
    }
    if (meta) return; // leave other modifier combos (copy/undo/…) to global handlers

    switch (e.key) {
      case " ": // Space → Configuration
        if (!onSettings) return;
        e.preventDefault();
        onSettings();
        break;
      case "Enter": // Enter → Rename
        e.preventDefault();
        setIsRenameDialogOpen(true);
        break;
      case "r":
      case "R": // R → Replace
        if (!canModify) return;
        e.preventDefault();
        nodeActions?.requestReplaceNode(id);
        break;
      case "d":
      case "D": // D → Activate / Deactivate
        if (!canModify) return;
        e.preventDefault();
        handleToggleActive();
        break;
      case "h":
      case "H": // H → Help
        e.preventDefault();
        setIsHelpDialogOpen(true);
        break;
      default:
        break;
    }
  };

  useEffect(() => {
    if (!selected) return;
    const handler = (e: KeyboardEvent) => nodeShortcutRef.current?.(e);
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [selected]);

  const nodeCategory = nodeDefinition?.category ?? "utils";
  // Header/frame background. Light mode keeps the soft pastel; dark mode uses a
  // SOLID dark shade of the node's own color — same hue, no transparency (values
  // live in nodeColors). The agent node uses the same treatment as the rest; its
  // only distinction is the animated gradient border (applied below).
  const cardBg = hasError
    ? "bg-red-200 dark:bg-[#330f10]"
    : isSpecialNode
    ? "bg-brand-600"
    : getNodeBgColor(nodeCategory);
  const iconColor = hasError ? "red-600" : isSpecialNode ? "white" : color;
  const icon = hasError ? "CircleAlert" : iconName;
  const docsUrl = getNodeDocsUrl(nodeType);
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
      className={`rounded-lg ${NODE_WIDTH} self-stretch ${
        isDeactivated
          ? `bg-transparent border-2 border-dashed ${
              selected ? "border-blue-500" : "border-muted-foreground/30"
            } opacity-80 grayscale`
          : `${cardBg} ${showAgentStyle ? "" : `border-2 ${getBorderColor()}`}`
      }`}
      style={{
        boxShadow:
          isDeactivated || showAgentStyle
            ? undefined
            : "0 0 10px rgba(0, 0, 0, 0.2)",
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
        deactivated={isDeactivated}
        onSettings={onSettings}
        onTest={handleTest}
        onHelpClick={() => setIsHelpDialogOpen(true)}
        onToggleActive={isSpecialNode ? undefined : handleToggleActive}
        onDeleteClick={() => setIsDeleteDialogOpen(true)}
        onRename={() => setIsRenameDialogOpen(true)}
        onReplace={() => nodeActions?.requestReplaceNode(id)}
        onCopy={() => nodeActions?.copyNode(id)}
        onDuplicate={() => nodeActions?.duplicateNode(id)}
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

  // Compact ("n8n-style") variant: an icon tile with the node name below it.
  // The tile is the sized element (name/toolbar are absolutely positioned) so
  // React Flow's handles stay vertically centered on the tile.
  //
  // Unlike the detailed card, the compact tile keeps the node's OWN icon and
  // color even when it hasn't been tested — the "not tested" state is shown as
  // a small alert row inside the tile instead of recoloring the whole node.
  const compactTileBg = isSpecialNode
    ? "bg-brand-600"
    : getNodeBgColor(nodeCategory);
  const compactIconColorClass = isSpecialNode
    ? "text-white"
    : getNodeIconColor(nodeCategory);

  const compactCard = (
    <div className="group relative" style={{ width: 144 }}>
      {/* Hover / selected action toolbar (parity with the detailed header) */}
      <div
        className={`absolute -top-9 left-1/2 z-30 flex -translate-x-1/2 items-center gap-0.5 rounded-full border border-border bg-card/95 px-1 py-0.5 shadow-md backdrop-blur-sm nodrag nopan pointer-events-auto transition-opacity ${
          selected ? "opacity-100" : "opacity-0 group-hover:opacity-100"
        }`}
      >
        {/* Order: play - settings - active/inactive - info - delete */}
        {isDeactivated ? (
          <TooltipProvider delayDuration={0}>
            <Tooltip>
              <TooltipTrigger asChild>
                {/* A disabled button swallows pointer events, so the span is the
                    hover target that drives the tooltip. */}
                <span className="inline-flex">
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-7 w-7"
                    disabled
                  >
                    <Play className="h-3.5 w-3.5" />
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent side="top">
                This node is deactivated and can't be run
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : (
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7"
            onClick={handleTest}
            title="Test"
          >
            <Play className="h-3.5 w-3.5" />
          </Button>
        )}
        {onSettings && (
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7"
            onClick={onSettings}
            data-node-settings
            title="Settings"
          >
            <Settings className="h-3.5 w-3.5" />
          </Button>
        )}
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7 text-red-600 hover:text-red-700"
          onClick={() => setIsDeleteDialogOpen(true)}
          title="Delete"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
        <NodeActionsMenu
          {...nodeMenuHandlers}
          canModify={!isSpecialNode}
          trigger={
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7"
              title="More actions"
            >
              <MoreVertical className="h-3.5 w-3.5" />
            </Button>
          }
        />
      </div>

      {/* Icon tile */}
      <div
        className={`relative flex h-[144px] w-[144px] items-center justify-center rounded-3xl ${
          isDeactivated
            ? `bg-transparent border-2 border-dashed ${
                selected ? "border-blue-500" : "border-muted-foreground/30"
              }`
            : `${compactTileBg} ${
                showAgentStyle
                  ? ""
                  : selected
                  ? "border-[3px] border-blue-500"
                  : "border-2 border-black/5 dark:border-white/10"
              }`
        }`}
        style={{
          boxShadow:
            isDeactivated || showAgentStyle
              ? undefined
              : "0 0 10px rgba(0, 0, 0, 0.15)",
        }}
      >
        {/* Node's own icon stays centered, exactly like a tested node. */}
        {renderIcon(
          iconName,
          `h-16 w-16 ${
            isDeactivated
              ? "text-muted-foreground opacity-60"
              : compactIconColorClass
          }`
        )}

        {/* Not-tested / validation indicator — a small alert badge in the
            bottom-right corner; the node keeps its own centered icon. */}
        {hasError && (
          <CircleAlert className="absolute bottom-2.5 right-2.5 h-5 w-5 text-red-500" />
        )}

        {/* Handlers anchor to this tile */}
        <HandlersRenderer id={id} data={data} />
      </div>

      {/* Node name below the tile */}
      <div
        className={`absolute left-1/2 top-full mt-3 w-[188px] -translate-x-1/2 break-words text-center text-sm font-medium leading-tight text-foreground ${
          isDeactivated ? "" : "line-clamp-2"
        }`}
        title={title}
      >
        {title}
        {isDeactivated && (
          <span className="block italic text-muted-foreground">
            (Deactivated)
          </span>
        )}
      </div>
    </div>
  );

  const renderCanvasNode = () => {
    if (isCompact) {
      if (showAgentStyle) {
        return (
          <div
            className={`agent-gradient-border${
              selected ? " ring-2 ring-blue-500 ring-offset-1" : ""
            }`}
            style={{
              borderRadius: 27,
              boxShadow: "0 0 16px rgba(192, 132, 252, 0.4)",
            }}
          >
            {compactCard}
          </div>
        );
      }
      return compactCard;
    }

    if (showAgentStyle) {
      return (
        <div
          className={`agent-gradient-border${selected ? " ring-2 ring-blue-500 ring-offset-1" : ""}`}
          style={{ boxShadow: "0 0 16px rgba(192, 132, 252, 0.4)" }}
        >
          {card}
        </div>
      );
    }
    return card;
  };

  return (
    <>
      {renderCanvasNode()}

      {/* Generic Test Dialog*/}
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

      <RenameNodeDialog
        isOpen={isRenameDialogOpen}
        onClose={() => setIsRenameDialogOpen(false)}
        currentName={data.name || ""}
        onRename={handleRename}
      />

      <Dialog open={isHelpDialogOpen} onOpenChange={setIsHelpDialogOpen}>
        <DialogContent className="w-[min(92vw,860px)] max-w-[860px] min-h-[420px] max-h-[90vh] p-0 overflow-hidden rounded-xl border border-border shadow-2xl">
          <div className="flex min-h-[420px] max-h-[90vh] flex-col bg-card">
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
                {docsUrl && (
                  <a
                    href={docsUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 inline-flex shrink-0 items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                  >
                    Docs
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}
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
