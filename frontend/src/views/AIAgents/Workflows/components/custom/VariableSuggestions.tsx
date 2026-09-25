import React, { useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  Braces,
  Brackets,
  ChevronDown,
  ChevronRight,
  Variable,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  VariableNode,
  VariableRow,
} from "@/helpers/variable-input/variableTree";

// The config panel sheet sits at 1002 and its alert dialog at 2000
const POPUP_Z_INDEX = 1100;
const POPUP_MAX_HEIGHT = 300;
const POPUP_WIDTH = 400;
const VIEWPORT_MARGIN = 8;
const INDENT_PX = 12;

/** Marks the popup so an ancestor scroll listener can ignore its own scrolling. */
export const SUGGESTIONS_ATTRIBUTE = "data-variable-suggestions";

function KindIcon({ kind }: { kind: VariableNode["kind"] }) {
  const className = "h-3 w-3 shrink-0";
  if (kind === "array") return <Brackets className={cn(className, "text-blue-500")} />;
  if (kind === "object") return <Braces className={cn(className, "text-blue-500")} />;
  return <Variable className={cn(className, "text-green-600 dark:text-green-500")} />;
}

interface VariableTreeRowsProps {
  rows: VariableRow[];
  activeIndex?: number;
  /** Show the full path under each label, useful while searching */
  showBreadcrumb?: boolean;
  onToggle: (path: string) => void;
  onHoverIndex?: (index: number) => void;
  /** Popup and picker: insert on press, without letting the field blur */
  onSelect?: (node: VariableNode) => void;
  /** Panel: drag a row into a field, or click to copy its path */
  onDragStartNode?: (e: React.DragEvent, node: VariableNode) => void;
  onCopyPath?: (node: VariableNode) => void;
}

/** The tree body, shared by the panel, the caret popup and the picker. */
export const VariableTreeRows: React.FC<VariableTreeRowsProps> = ({
  rows,
  activeIndex,
  showBreadcrumb,
  onToggle,
  onHoverIndex,
  onSelect,
  onDragStartNode,
  onCopyPath,
}) => (
  <>
    {rows.map((row, index) => {
      const active = activeIndex !== undefined && index === activeIndex;
      return (
        <div
          key={row.node.path}
          role="option"
          aria-selected={activeIndex === undefined ? undefined : active}
          aria-expanded={row.expandable ? row.expanded : undefined}
          draggable={onDragStartNode ? true : undefined}
          onDragStart={
            onDragStartNode ? (e) => onDragStartNode(e, row.node) : undefined
          }
          onMouseEnter={onHoverIndex ? () => onHoverIndex(index) : undefined}
          // Selecting has to beat the blur, so it happens on press. Suppressing
          // the default would also cancel a drag, so panel rows use onClick.
          onMouseDown={
            onSelect
              ? (e) => {
                  e.preventDefault();
                  onSelect(row.node);
                }
              : undefined
          }
          onClick={onCopyPath ? () => onCopyPath(row.node) : undefined}
          title={onDragStartNode ? "Click to copy • Drag to a field" : undefined}
          className={cn(
            "flex items-center gap-1.5 rounded-sm py-1 pr-2 transition-colors",
            onDragStartNode ? "cursor-grab active:cursor-grabbing" : "cursor-pointer",
            active ? "bg-accent text-accent-foreground" : "hover:bg-accent/50"
          )}
          style={{ paddingLeft: 4 + row.depth * INDENT_PX }}
        >
          {row.expandable ? (
            <button
              type="button"
              tabIndex={-1}
              aria-label={row.expanded ? "Collapse" : "Expand"}
              className="shrink-0 rounded p-0.5 text-muted-foreground hover:text-foreground"
              onMouseDown={(e) => {
                // Toggling must not also insert the variable
                e.preventDefault();
                e.stopPropagation();
                onToggle(row.node.path);
              }}
            >
              {row.expanded ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
            </button>
          ) : (
            <span className="w-4 shrink-0" />
          )}

          <KindIcon kind={row.node.kind} />

          <div className="min-w-0 flex-1">
            <div className="truncate text-xs font-medium">{row.node.label}</div>
            {showBreadcrumb && (
              <div className="truncate text-[11px] text-muted-foreground">
                {row.node.breadcrumb}
              </div>
            )}
          </div>

          <span className="max-w-[40%] truncate font-mono text-[11px] text-muted-foreground">
            {row.node.preview}
          </span>
        </div>
      );
    })}
  </>
);

/**
 * Shown instead of the tree when there is nothing to offer. Without this the
 * popup would simply not appear, leaving no clue why "{{" did nothing.
 */
export const VariableEmptyState: React.FC<{ filtered: boolean }> = ({
  filtered,
}) => (
  <p className="px-3 py-6 text-center text-xs text-muted-foreground">
    {filtered
      ? "No matching variables."
      : "Connect this node to the workflow to see available data."}
  </p>
);

interface VariableSuggestionsProps {
  /** Caret position in viewport coordinates */
  anchor: { top: number; left: number };
  rows: VariableRow[];
  activeIndex: number;
  showBreadcrumb?: boolean;
  /** True when rows are empty only because the query filtered them out */
  filtered?: boolean;
  onSelect: (node: VariableNode) => void;
  onToggle: (path: string) => void;
  onHoverIndex: (index: number) => void;
}

/**
 * Caret-anchored tree shown while a "{{" trigger is open. Rendered in a portal
 * so it escapes the config panel's clipped, scrolling containers.
 */
export const VariableSuggestions: React.FC<VariableSuggestionsProps> = ({
  anchor,
  rows,
  activeIndex,
  showBreadcrumb,
  filtered,
  onSelect,
  onToggle,
  onHoverIndex,
}) => {
  const listRef = useRef<HTMLDivElement>(null);
  const [placement, setPlacement] = useState<{ top: number; left: number }>(anchor);

  useLayoutEffect(() => {
    const el = listRef.current;
    if (!el) return;

    const height = el.offsetHeight;
    const width = el.offsetWidth;

    // Flip above the caret when the list would run off the bottom
    const fitsBelow = anchor.top + height <= window.innerHeight - VIEWPORT_MARGIN;
    const top = fitsBelow
      ? anchor.top
      : Math.max(VIEWPORT_MARGIN, anchor.top - height - 20);

    const left = Math.max(
      VIEWPORT_MARGIN,
      Math.min(anchor.left, window.innerWidth - width - VIEWPORT_MARGIN)
    );

    setPlacement({ top, left });
  }, [anchor, rows.length]);

  // Keep the highlighted row visible while arrowing through a long tree
  useLayoutEffect(() => {
    const active = listRef.current?.querySelector<HTMLElement>(
      '[aria-selected="true"]'
    );
    active?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  return createPortal(
    <div
      ref={listRef}
      role="listbox"
      {...{ [SUGGESTIONS_ATTRIBUTE]: "" }}
      className="fixed overflow-y-auto overscroll-contain rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
      style={{
        top: placement.top,
        left: placement.left,
        width: POPUP_WIDTH,
        maxHeight: POPUP_MAX_HEIGHT,
        zIndex: POPUP_Z_INDEX,
      }}
    >
      {rows.length === 0 ? (
        <VariableEmptyState filtered={Boolean(filtered)} />
      ) : (
        <VariableTreeRows
          rows={rows}
          activeIndex={activeIndex}
          showBreadcrumb={showBreadcrumb}
          onSelect={onSelect}
          onToggle={onToggle}
          onHoverIndex={onHoverIndex}
        />
      )}
    </div>,
    document.body
  );
};
