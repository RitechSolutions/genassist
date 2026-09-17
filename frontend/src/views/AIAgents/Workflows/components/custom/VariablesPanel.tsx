import React, { useCallback, useState } from "react";
import { PanelLeftClose } from "lucide-react";
import { Button } from "@/components/button";
import type { VariableNode } from "@/helpers/variable-input/variableTree";
import {
  applyVariableDragImage,
  setVariableDragData,
} from "@/helpers/variable-input/variableDragDrop";
import { useWorkflowVariables } from "../../context/WorkflowVariablesContext";
import { useVariableTree } from "../../hooks/useVariableTree";
import { VariableEmptyState, VariableTreeRows } from "./VariableSuggestions";

interface VariablesPanelProps {
  onCollapse: () => void;
}

/**
 * Browsable list of the data available to this node, for dragging into fields
 * or copying a path. Collapsed by default — typing "{{" in a field reaches the
 * same tree without giving up the width.
 */
export const VariablesPanel: React.FC<VariablesPanelProps> = ({ onCollapse }) => {
  const { tree } = useWorkflowVariables();
  const { rows, toggle } = useVariableTree(tree, "");
  const [copied, setCopied] = useState<string | null>(null);

  const handleDragStart = useCallback(
    (e: React.DragEvent, node: VariableNode) => {
      setVariableDragData(e.dataTransfer, node.path);
      applyVariableDragImage(e.dataTransfer, node.reference);
    },
    []
  );

  const handleCopy = useCallback((node: VariableNode) => {
    navigator.clipboard?.writeText(node.reference);
    setCopied(node.path);
    window.setTimeout(() => setCopied(null), 1200);
  }, []);

  return (
    <div className="min-w-72 max-w-sm flex-1 border-r border-border pr-4 flex flex-col py-6">
      <div className="flex items-center justify-between gap-3 mb-3 pb-3 border-b border-border">
        <p className="text-xs text-muted-foreground">
          {copied ? "Copied to clipboard" : "Drag variables into fields"}
        </p>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={onCollapse}
          title="Hide variables panel"
          aria-label="Hide variables panel"
        >
          <PanelLeftClose className="h-4 w-4 text-muted-foreground" />
        </Button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto rounded-lg border border-border bg-card p-1">
        {rows.length === 0 ? (
          <VariableEmptyState filtered={false} />
        ) : (
          <VariableTreeRows
            rows={rows}
            onToggle={toggle}
            onDragStartNode={handleDragStart}
            onCopyPath={handleCopy}
          />
        )}
      </div>
    </div>
  );
};
