import { useState, useEffect } from "react";
import { DataTable } from "@/components/DataTable";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { TableCell, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { LLMAnalyst } from "@/interfaces/llmAnalyst.interface";
import { toast } from "react-hot-toast";

interface LLMAnalystCardProps {
  analysts: LLMAnalyst[];
  searchQuery: string;
  onEdit: (analyst: LLMAnalyst) => void;
  onDelete: (id: string) => Promise<void>;
}

export function LLMAnalystCard({
  analysts,
  searchQuery,
  onEdit,
  onDelete,
}: LLMAnalystCardProps) {
  const [loading, setLoading] = useState(true);
  const [analystToDelete, setAnalystToDelete] = useState<LLMAnalyst | null>(
    null
  );
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setLoading(false);
    }, 2000);
    return () => clearTimeout(timeout);
  }, [analysts]);

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

  const headers = ["Name", "Provider", "Prompt", "Status", "Actions"];

  const renderRow = (analyst: LLMAnalyst) => (
    <TableRow key={analyst.id}>
      <TableCell className="font-medium break-all">{analyst.name}</TableCell>
      <TableCell className="truncate">{analyst.llm_provider?.name}</TableCell>
      <TableCell>
        <span className="line-clamp-2">{analyst.prompt}</span>
      </TableCell>
      <TableCell className="overflow-hidden whitespace-nowrap text-clip">
        <Badge variant={analyst.is_active ? "default" : "secondary"}>
          {analyst.is_active ? "Active" : "Inactive"}
        </Badge>
      </TableCell>
      <TableCell>
        <ActionButtons
          onEdit={() => onEdit(analyst)}
          onDelete={() => handleDeleteClick(analyst)}
          editTitle="Edit"
          deleteTitle="Delete"
        />
      </TableCell>
    </TableRow>
  );

  return (
    <>
      <DataTable
        data={filtered}
        loading={loading}
        searchQuery={searchQuery}
        headers={headers}
        renderRow={renderRow}
        emptyMessage="No LLM Analysts found"
        searchEmptyMessage="No LLM Analysts found matching your search"
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
