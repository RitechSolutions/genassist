import React from "react";
import { X } from "lucide-react";
import nodeRegistry from "@/views/AIAgents/Workflows/registry/nodeRegistry";
import { renderIcon } from "@/views/AIAgents/Workflows/utils/iconUtils";
import { getNodeBgColor, getNodeIconColor } from "@/views/AIAgents/Workflows/utils/nodeColors";
import { cn } from "@/lib/utils";
import { splitNodeMentions, type MentionableNode } from "@/views/AIAgents/Workflows/utils/assistantDraft";

export interface NodeChipProps {
  node: MentionableNode;
  onClick?: (nodeId: string) => void;
  onRemove?: (nodeId: string) => void;
  /** Dashed, quieter chip for context that was not typed by the person (the selected node). */
  soft?: boolean;
  /** On a dark bubble (the person's own messages). */
  inverted?: boolean;
}

/**
 * The node's icon on its category-coloured tile, as the canvas draws it, shrunk
 * to text size. Also what the "@" picker shows next to each step.
 */
export const NodeMiniIcon: React.FC<{ type?: string; className?: string }> = ({ type, className }) => {
  const definition = type ? nodeRegistry.getNodeType(type) : undefined;
  if (!definition) return null;
  const category = definition.category || "default";
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-[5px] [&>svg]:h-[62%] [&>svg]:w-[62%]",
        getNodeBgColor(category),
        className ?? "h-4 w-4"
      )}
    >
      {renderIcon(definition.icon, cn("h-full w-full", getNodeIconColor(category)))}
    </span>
  );
};

/** A step of the workflow as a miniature of its node: icon tile and name. Clicking it centres the canvas on the step. */
export const NodeChip: React.FC<NodeChipProps> = ({ node, onClick, onRemove, soft, inverted }) => {
  // On the person's own blue bubble there is no chip at all: the icon tile and the name in
  // italics, inline with the text.
  const base = inverted
    ? "border-transparent bg-transparent px-0 text-white"
    : soft
    ? "border-dashed border-border bg-muted/40 text-muted-foreground hover:bg-muted"
    : "border-dashed border-border bg-muted/30 text-foreground hover:bg-muted";
  return (
    <span
      className={`inline-flex max-w-full items-center gap-1 rounded-[6px] border py-0.5 pl-1 pr-1.5 align-middle text-[12px] leading-4 ${base}`}
    >
      <button
        type="button"
        onClick={() => onClick?.(node.id)}
        title="Show this step on the canvas"
        className="inline-flex min-w-0 items-center gap-1.5"
      >
        <NodeMiniIcon type={node.type} />
        <span className={cn("truncate font-medium", inverted && "italic")}>{node.name}</span>
      </button>
      {onRemove && (
        <button
          type="button"
          onClick={() => onRemove(node.id)}
          aria-label={`Remove ${node.name}`}
          className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full hover:bg-black/10 dark:hover:bg-white/10"
        >
          <X className="h-2.5 w-2.5" />
        </button>
      )}
    </span>
  );
};

/** A message with every "@Step" or quoted step name shown as a chip. */
export const MentionText: React.FC<{
  text: string;
  nodes: MentionableNode[];
  /** Ids of the steps the message was sent about; they win when two steps share a name. */
  preferIds?: string[];
  onFocusNode?: (nodeId: string) => void;
  inverted?: boolean;
}> = ({ text, nodes, preferIds, onFocusNode, inverted }) => {
  const segments = splitNodeMentions(text, nodes, preferIds);
  return (
    <span className="whitespace-pre-wrap">
      {segments.map((segment, index) =>
        "node" in segment ? (
          <NodeChip key={index} node={segment.node} onClick={onFocusNode} inverted={inverted} />
        ) : (
          <React.Fragment key={index}>{segment.text}</React.Fragment>
        )
      )}
    </span>
  );
};

/** The steps a message names, as a row of chips under it (keeps the message's own formatting). */
export const MentionedNodesRow: React.FC<{
  text: string;
  nodes: MentionableNode[];
  preferIds?: string[];
  onFocusNode?: (nodeId: string) => void;
}> = ({ text, nodes, preferIds, onFocusNode }) => {
  const mentioned = splitNodeMentions(text, nodes, preferIds)
    .filter((segment): segment is { node: MentionableNode } => "node" in segment)
    .map((segment) => segment.node)
    .filter((node, index, all) => all.findIndex((n) => n.id === node.id) === index);
  if (mentioned.length === 0) return null;
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1">
      {mentioned.map((node) => (
        <NodeChip key={node.id} node={node} onClick={onFocusNode} />
      ))}
    </div>
  );
};
