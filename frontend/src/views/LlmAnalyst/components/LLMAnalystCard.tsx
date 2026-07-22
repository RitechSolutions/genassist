import { useEffect, useRef, useState } from "react";
import { DataTable, Column } from "@/components/ui/data-table";
import { LIST_PAGE_SIZE } from "@/constants/pagination";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge } from "@/components/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/RadixTooltip";
import { LLMAnalyst } from "@/interfaces/llmAnalyst.interface";
import { toast } from "react-hot-toast";

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
  );
}

export function LLMAnalystCard({
  analysts,
  searchQuery,
  loading = false,
  onEdit,
  onDelete,
}: LLMAnalystCardProps) {
  const [analystToDelete, setAnalystToDelete] = useState<LLMAnalyst | null>(
    null
  );
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const filtered = analysts.filter((a) => {
    const name = a.name?.toLowerCase() || "";
    const provider = a.llm_provider?.name?.toLowerCase() || "";
    return (
      name.includes(searchQuery.toLowerCase()) ||
      provider.includes(searchQuery.toLowerCase())
    );
  });

  const handleDeleteClick = (analyst: LLMAnalyst) => {
    setAnalystToDelete(analyst);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!analystToDelete?.id) return;

    try {
      setIsDeleting(true);
      await onDelete(analystToDelete.id);
      toast.success("LLM analyst deleted successfully.");
    } catch (error) {
      toast.error("Failed to delete LLM analyst.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setAnalystToDelete(null);
    }
  };

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
    {
      header: "Actions",
      key: "actions",
      cell: (analyst) => (
        <ActionButtons
          onEdit={() => onEdit(analyst)}
          onDelete={() => handleDeleteClick(analyst)}
          editTitle="Edit"
          deleteTitle="Delete"
        />
      ),
    },
  ];

  return (
    <>
      <TooltipProvider delayDuration={200}>
        <DataTable
          data={filtered}
          columns={columns}
          loading={loading}
          searchQuery={searchQuery}
          pageSize={LIST_PAGE_SIZE}
          emptyMessage="No LLM Analysts found"
          notFoundMessage="No LLM Analysts found matching your search"
        />
      </TooltipProvider>

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isInProgress={isDeleting}
        itemName={analystToDelete?.name || ""}
        description={`This action cannot be undone. This will permanently delete the LLM Analyst "${analystToDelete?.name}".`}
      />
    </>
  );
}
