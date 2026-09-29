import React, { memo } from "react";
import {
  NodeProps,
  NodeResizeControl,
  ResizeControlVariant,
  useStore,
  type ReactFlowState,
} from "reactflow";
import { Check, Group, Maximize, MoreHorizontal, Pencil, Trash2, Ungroup } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/dropdown-menu";
import { useNodeActions } from "../../context/NodeActionsContext";
import {
  DEFAULT_GROUP_NAME,
  GROUP_MIN_HEIGHT,
  GROUP_MIN_WIDTH,
  GROUP_PADDING,
  GroupNodeData,
  getParentId,
} from "../../utils/nodeGroups";
import { GROUP_COLORS, getGroupColor } from "./groupColors";

// Smallest size the resizer allows: the group must still frame its children. Returned as a
// string so the store selector only re-renders this group when the numbers actually change.
const selectChildExtent =
  (groupId: string) =>
  (s: ReactFlowState): string => {
    let count = 0;
    let right = 0;
    let bottom = 0;
    s.nodeInternals.forEach((node) => {
      if (getParentId(node) !== groupId) return;
      count += 1;
      right = Math.max(right, node.position.x + (node.width ?? 0));
      bottom = Math.max(bottom, node.position.y + (node.height ?? 0));
    });
    return `${count}|${right}|${bottom}`;
  };

const resizeLineStyle = { borderColor: "transparent", borderWidth: 4 };

/**
 * Visual-only container that frames a set of related nodes under a name. It has no handles and
 * isn't registered in the node registry, so it can't be connected, configured or executed — the
 * backend engine also drops it (see utils/nodeGroups for the data model).
 *
 * Resizing is limited to the right/bottom edges: growing from the top/left would move the group's
 * origin, and with it every child (their positions are relative to it).
 */
const GroupNode: React.FC<NodeProps<GroupNodeData>> = ({ id, data, selected }) => {
  const actions = useNodeActions();
  const [countStr, rightStr, bottomStr] = useStore(selectChildExtent(id)).split("|");
  const childCount = Number(countStr);
  const minWidth = Math.max(GROUP_MIN_WIDTH, Number(rightStr) + GROUP_PADDING / 2);
  const minHeight = Math.max(GROUP_MIN_HEIGHT, Number(bottomStr) + GROUP_PADDING / 2);
  const name = data?.name?.trim() || DEFAULT_GROUP_NAME;
  const color = getGroupColor(data?.color);
  // A coloured group tints its border, fill and title; the default keeps the neutral theme look.
  const tint = color.rgb
    ? {
        container: {
          borderColor: `rgb(${color.rgb} / ${selected ? 0.9 : 0.55})`,
          backgroundColor: `rgb(${color.rgb} / ${selected ? 0.1 : 0.07})`,
        },
        accent: { color: `rgb(${color.rgb})` },
      }
    : null;

  // Radix closes the menu on select; defer so a dialog opened by the action isn't dismissed by the
  // menu's own close handling (same approach as NodeActionsMenu).
  const run = (fn?: (groupId: string) => void) => () => {
    if (fn) setTimeout(() => fn(id), 0);
  };

  return (
    <div
      className={`wf-group h-full w-full rounded-2xl border-2 transition-colors ${
        tint
          ? selected
            ? "border-solid"
            : "border-dashed"
          : selected
            ? "border-blue-500/70 bg-blue-500/[0.06] dark:bg-blue-400/[0.06]"
            : "border-dashed border-border bg-muted/40 dark:border-white/15 dark:bg-white/[0.03]"
      }`}
      style={tint?.container}
    >
      <div className="flex h-14 items-center gap-2.5 px-5">
        <Group className="h-5 w-5 shrink-0 text-muted-foreground" style={tint?.accent} />
        <span
          className="min-w-0 truncate text-lg font-semibold text-foreground/80"
          style={tint?.accent}
          title="Double-click to rename"
          onDoubleClick={(e) => {
            e.stopPropagation();
            actions?.renameGroup(id);
          }}
        >
          {name}
        </span>
        <span className="shrink-0 text-sm text-muted-foreground">
          {childCount} {childCount === 1 ? "node" : "nodes"}
        </span>
        {actions && (
          <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label="Group actions"
                className="nodrag ml-auto rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <MoreHorizontal className="h-4 w-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" sideOffset={6} className="z-[2100] min-w-[220px]">
              <DropdownMenuItem onSelect={run(actions.renameGroup)}>
                <Pencil className="mr-2 h-4 w-4" />
                Rename
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={run(actions.fitGroup)} disabled={childCount === 0}>
                <Maximize className="mr-2 h-4 w-4" />
                Fit to contents
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={run(actions.ungroup)}>
                <Ungroup className="mr-2 h-4 w-4" />
                Ungroup
                <DropdownMenuShortcut>⇧⌘G</DropdownMenuShortcut>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">
                Color
              </DropdownMenuLabel>
              <div className="grid grid-cols-9 gap-1.5 px-2 pb-2 pt-0.5">
                {GROUP_COLORS.map((option) => {
                  const active = option.key === color.key;
                  return (
                    <button
                      key={option.key}
                      type="button"
                      title={option.label}
                      aria-label={`${option.label} color`}
                      aria-pressed={active}
                      onClick={() => actions.setGroupColor(id, option.key)}
                      className={`flex h-5 w-5 items-center justify-center rounded-full border transition-transform hover:scale-110 ${
                        option.rgb ? "border-transparent" : "border-border bg-muted"
                      } ${active ? "ring-2 ring-foreground/60 ring-offset-1 ring-offset-popover" : ""}`}
                      style={option.rgb ? { backgroundColor: `rgb(${option.rgb})` } : undefined}
                    >
                      {active && (
                        <Check
                          className={`h-3 w-3 ${option.rgb ? "text-white" : "text-foreground"}`}
                        />
                      )}
                    </button>
                  );
                })}
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onSelect={run(actions.requestDeleteGroup)}
                className="text-destructive focus:text-destructive"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete group…
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      {selected && (
        <>
          <NodeResizeControl
            position="right"
            variant={ResizeControlVariant.Line}
            style={resizeLineStyle}
            minWidth={minWidth}
            minHeight={minHeight}
          />
          <NodeResizeControl
            position="bottom"
            variant={ResizeControlVariant.Line}
            style={resizeLineStyle}
            minWidth={minWidth}
            minHeight={minHeight}
          />
          <NodeResizeControl
            position="bottom-right"
            minWidth={minWidth}
            minHeight={minHeight}
            style={{
              width: 12,
              height: 12,
              borderRadius: 3,
              background: "hsl(var(--background))",
              border: "2px solid rgb(59 130 246 / 0.8)",
            }}
          />
        </>
      )}
    </div>
  );
};

export default memo(GroupNode);
