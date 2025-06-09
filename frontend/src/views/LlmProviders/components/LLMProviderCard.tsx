import { useState } from "react";
import { DataTable } from "@/components/DataTable";
import { ActionButtons } from "@/components/ActionButtons";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { TableCell, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { toast } from "react-hot-toast";

interface LLMProviderCardProps {
  providers: LLMProvider[];
  searchQuery: string;
  loading: boolean;
  onEdit: (provider: LLMProvider) => void;
  onDelete: (id: string) => Promise<void>;
}

export function LLMProviderCard({
  providers,
  searchQuery,
  loading,
  onEdit,
  onDelete,
}: LLMProviderCardProps) {
  const [providerToDelete, setProviderToDelete] = useState<LLMProvider | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const filtered = providers.filter((p) => {
    const name = p.name.toLowerCase();
    const type = p.llm_model_provider.toLowerCase();
    const model = p.llm_model.toLowerCase();
    return (
      name.includes(searchQuery.toLowerCase()) ||
      type.includes(searchQuery.toLowerCase()) ||
      model.includes(searchQuery.toLowerCase())
    );
  });

  const handleDeleteClick = (provider: LLMProvider) => {
    setProviderToDelete(provider);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!providerToDelete?.id) return;

    try {
      setIsDeleting(true);
      await onDelete(providerToDelete.id);
      toast.success("LLM Provider deleted successfully");
    } catch (error) {
      toast.error("Failed to delete LLM Provider");
      console.error("Delete error:", error);
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setProviderToDelete(null);
    }
  };

  const headers = ["Name", "Type", "Model", "Status", "Actions"];

  const renderRow = (provider: LLMProvider) => (
    <TableRow key={provider.id}>
      <TableCell>{provider.name}</TableCell>
      <TableCell>{provider.llm_model_provider}</TableCell>
      <TableCell>{provider.llm_model}</TableCell>
      <TableCell>
        <Badge variant={provider.is_active ? "default" : "secondary"}>
          {provider.is_active ? "Active" : "Inactive"}
        </Badge>
      </TableCell>
      <TableCell>
        <ActionButtons
          onEdit={() => onEdit(provider)}
          onDelete={() => handleDeleteClick(provider)}
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
        emptyMessage="No LLM Providers found"
        searchEmptyMessage="No LLM Providers matching your search"
      />

      <DeleteConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isDeleting={isDeleting}
        itemName={providerToDelete?.name || ""}
        description={`This action cannot be undone. This will permanently delete the provider "${providerToDelete?.name}".`}
      />
    </>
  );
}
