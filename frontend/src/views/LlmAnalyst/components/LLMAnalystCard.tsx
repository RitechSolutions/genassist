import { useEffect, useRef, useState } from "react";
import { Column } from "@/components/ui/data-table";
import { EntityTableCard } from "@/components/EntityTableCard";
import { Badge } from "@/components/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/RadixTooltip";
import { LLMAnalyst } from "@/interfaces/llmAnalyst.interface";

interface LLMAnalystCardProps {
  analysts: LLMAnalyst[];
  searchQuery: string;
  loading?: boolean;
  onEdit: (analyst: LLMAnalyst) => void;
  onDelete: (id: string) => Promise<void>;
}

// Reveals the full prompt on hover only when the cell text is truncated
function PromptCell({ prompt }: { prompt: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [isTruncated, setIsTruncated] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setIsTruncated(el.scrollWidth > el.clientWidth);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [prompt]);

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span ref={ref} className="block truncate">
            {prompt}
          </span>
        </TooltipTrigger>
        {isTruncated && (
          <TooltipContent className="max-w-md whitespace-pre-wrap break-words">
            {prompt}
          </TooltipContent>
        )}
      </Tooltip>
    </TooltipProvider>
  );
}

export function LLMAnalystCard({
  analysts,
  searchQuery,
  loading = false,
  onEdit,
  onDelete,
}: LLMAnalystCardProps) {
  const columns: Column<LLMAnalyst>[] = [
    {
      header: "Name",
      key: "name",
      cell: (analyst) => analyst.name,
      className: "font-medium break-all",
    },
    {
      header: "Provider",
      key: "provider",
      cell: (analyst) => analyst.llm_provider?.name,
      className: "truncate",
    },
    {
      header: "Prompt",
      key: "prompt",
      headerClassName: "w-[360px]",
      className: "max-w-[360px]",
      cell: (analyst) => <PromptCell prompt={analyst.prompt} />,
    },
    {
      header: "Status",
      key: "status",
      className: "overflow-hidden whitespace-nowrap text-clip",
      cell: (analyst) => (
        <Badge variant={analyst.is_active ? "default" : "secondary"}>
          {analyst.is_active ? "Active" : "Inactive"}
        </Badge>
      ),
    },
  ];

  return (
    <EntityTableCard<LLMAnalyst>
      data={analysts}
      loading={loading}
      searchQuery={searchQuery}
      filterFn={(analyst, query) => {
        const q = query.toLowerCase();
        const name = analyst.name?.toLowerCase() || "";
        const provider = analyst.llm_provider?.name?.toLowerCase() || "";
        return name.includes(q) || provider.includes(q);
      }}
      deleteFn={(analyst) => onDelete(analyst.id!)}
      getItemName={(analyst) => analyst.name}
      deleteDescription={(analyst) =>
        `This action cannot be undone. This will permanently delete the LLM Analyst "${analyst.name}".`
      }
      deleteSuccessMessage="LLM analyst deleted successfully."
      deleteErrorMessage="Failed to delete LLM analyst."
      emptyMessage="No LLM Analysts found"
      notFoundMessage="No LLM Analysts found matching your search"
      columns={columns}
      rowActions={{
        onEdit,
        editTitle: "Edit",
        deleteTitle: "Delete",
      }}
    />
  );
}
