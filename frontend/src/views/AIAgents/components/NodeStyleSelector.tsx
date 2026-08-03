import React from "react";
import { Boxes, Check, LayoutGrid } from "lucide-react";
import { cn } from "@/helpers/utils";
import {
  DEFAULT_NODE_STYLE,
  WorkflowNodeStyle,
} from "@/interfaces/workflow.interface";

interface NodeStyleSelectorProps {
  value: WorkflowNodeStyle;
  onChange: (style: WorkflowNodeStyle) => void;
}

interface StyleOption {
  value: WorkflowNodeStyle;
  title: string;
  description: string;
  preview: React.ReactNode;
}

// A miniature mock of the "detailed" full card (header + config rows).
const DetailedPreview: React.FC = () => (
  <div className="w-full rounded-md border border-border bg-card shadow-sm">
    <div className="flex items-center gap-2 border-b border-border px-2.5 py-2">
      <div className="flex h-5 w-5 items-center justify-center rounded bg-sky-500/80">
        <LayoutGrid className="h-3 w-3 text-white" />
      </div>
      <div className="flex-1 space-y-1">
        <div className="h-1.5 w-14 rounded-full bg-muted-foreground/60" />
        <div className="h-1 w-10 rounded-full bg-muted-foreground/30" />
      </div>
    </div>
    <div className="space-y-1.5 px-2.5 py-2">
      <div className="h-1 w-full rounded-full bg-muted-foreground/25" />
      <div className="h-1 w-3/4 rounded-full bg-muted-foreground/25" />
    </div>
  </div>
);

// A miniature mock of the "compact" n8n-style icon tile with the name below.
const CompactPreview: React.FC = () => (
  <div className="flex flex-col items-center gap-1.5 py-1.5">
    <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-sky-50 shadow-sm dark:bg-[#082231]">
      <Boxes className="h-5 w-5 text-sky-600" />
    </div>
    <div className="h-1.5 w-12 rounded-full bg-muted-foreground/50" />
  </div>
);

const STYLE_OPTIONS: StyleOption[] = [
  {
    value: "detailed",
    title: "Detailed",
    description: "Full cards with header and configuration preview.",
    preview: <DetailedPreview />,
  },
  {
    value: "compact",
    title: "Compact",
    description: "Icon-only tiles with the node name below.",
    preview: <CompactPreview />,
  },
];

/**
 * Node style radio group (Detailed / Compact) for a workflow's canvas rendering.
 * Controlled via `value`/`onChange`; the preference is persisted with the workflow.
 */
const NodeStyleSelector: React.FC<NodeStyleSelectorProps> = ({
  value,
  onChange,
}) => {
  const selected = value ?? DEFAULT_NODE_STYLE;

  return (
    <div
      role="radiogroup"
      aria-label="Node style"
      className="grid grid-cols-2 gap-3"
    >
      {STYLE_OPTIONS.map((option) => {
        const isActive = selected === option.value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={isActive}
            onClick={() => onChange(option.value)}
            className={cn(
              "group relative flex flex-col rounded-lg border-2 p-3 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              isActive
                ? "border-blue-500 bg-blue-500/5"
                : "border-border hover:border-muted-foreground/40"
            )}
          >
            {isActive && (
              <span className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-blue-500 text-white">
                <Check className="h-3 w-3" />
              </span>
            )}
            <div className="flex h-[72px] items-center justify-center rounded-md bg-muted/40 px-3">
              {option.preview}
            </div>
            <div className="mt-2.5 text-sm font-semibold text-foreground">
              {option.title}
            </div>
            <div className="mt-0.5 text-xs leading-snug text-muted-foreground">
              {option.description}
            </div>
          </button>
        );
      })}
    </div>
  );
};

export default NodeStyleSelector;
