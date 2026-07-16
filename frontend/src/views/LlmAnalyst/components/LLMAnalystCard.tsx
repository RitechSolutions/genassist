import { useState } from "react";
import { DataTable, Column } from "@/components/ui/data-table";
import { LIST_PAGE_SIZE } from "@/constants/pagination";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge } from "@/components/badge";
import { LLMAnalyst } from "@/interfaces/llmAnalyst.interface";
import { toast } from "react-hot-toast";

interface LLMAnalystCardProps {
  analysts: LLMAnalyst[];
  searchQuery: string;
  loading?: boolean;
  onEdit: (analyst: LLMAnalyst) => void;
  onDelete: (id: string) => Promise<void>;
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
      cell: (analyst) => <span className="line-clamp-2">{analyst.prompt}</span>,
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
      <DataTable
        data={filtered}
        columns={columns}
        loading={loading}
        searchQuery={searchQuery}
        pageSize={LIST_PAGE_SIZE}
        emptyMessage="No LLM Analysts found"
        notFoundMessage="No LLM Analysts found matching your search"
      />

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
