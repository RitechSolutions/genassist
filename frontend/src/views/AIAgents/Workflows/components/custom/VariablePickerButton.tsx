import React, { useRef, useState } from "react";
import { Braces, Search } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import { Button } from "@/components/button";
import { cn } from "@/lib/utils";
import type { VariableNode } from "@/helpers/variable-input/variableTree";
import { useWorkflowVariables } from "../../context/WorkflowVariablesContext";
import { useVariableTree } from "../../hooks/useVariableTree";
import { VariableEmptyState, VariableTreeRows } from "./VariableSuggestions";

// Above the config panel sheet (1002), below its alert dialog (2000)
const POPOVER_Z_INDEX = 1100;

interface VariablePickerButtonProps {
  onSelect: (option: VariableNode) => void;
  className?: string;
}

/**
 * Per-field entry point to the variable tree, for people who do not know the
 * "{{" shortcut. Backed by the same data as the typeahead and drag & drop.
 */
export const VariablePickerButton: React.FC<VariablePickerButtonProps> = ({
  onSelect,
  className,
}) => {
  const { tree } = useWorkflowVariables();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  const { rows, activeIndex, setActiveIndex, toggle, handleKey } = useVariableTree(
    tree,
    query
  );

  const handleSelect = (option: VariableNode) => {
    setOpen(false);
    setQuery("");
    onSelect(option);
  };

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) setQuery("");
  };

  // Keep the highlighted row in view while arrowing from the search box
  React.useLayoutEffect(() => {
    listRef.current
      ?.querySelector<HTMLElement>('[aria-selected="true"]')
      ?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          title="Insert variable"
          aria-label="Insert variable"
          className={cn(
            "h-7 w-7 text-muted-foreground transition-opacity hover:text-foreground",
            // Quiet at rest, so a column of these reads as controls rather than
            // decoration. Comes forward for the field you are actually in.
            "opacity-40 group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100",
            open && "opacity-100",
            className
          )}
          // Keep the field's caret intact when opening the picker
          onMouseDown={(e) => e.preventDefault()}
        >
          <Braces className="h-3.5 w-3.5" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-[400px] p-0"
        style={{ zIndex: POPOVER_Z_INDEX }}
      >
        <div className="flex items-center gap-2 border-b px-3">
          <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") return;
              if (handleKey(e.key, handleSelect)) e.preventDefault();
            }}
            placeholder="Search variables…"
            className="h-9 w-full bg-transparent text-xs outline-none placeholder:text-muted-foreground"
          />
        </div>
        <div ref={listRef} className="max-h-[300px] overflow-y-auto p-1">
          {rows.length === 0 ? (
            <VariableEmptyState filtered={tree.length > 0} />
          ) : (
            <VariableTreeRows
              rows={rows}
              activeIndex={activeIndex}
              showBreadcrumb={query.length > 0}
              onSelect={handleSelect}
              onToggle={toggle}
              onHoverIndex={setActiveIndex}
            />
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
};
