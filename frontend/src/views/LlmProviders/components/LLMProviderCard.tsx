import { useEffect, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { TableCell, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { getAllLLMProviders, deleteLLMProvider } from "@/services/llmProviders";
import { toast } from "react-hot-toast";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle, AlertCircle, HelpCircle } from 'lucide-react';

interface LLMProviderCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEdit: (provider: LLMProvider) => void;
  updatedProvider?: LLMProvider | null;
}

export function LLMProviderCard({
  searchQuery,
  refreshKey = 0,
  onEdit,
  updatedProvider = null,
}: LLMProviderCardProps) {
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [providerToDelete, setProviderToDelete] = useState<LLMProvider | null>(
    null
  );
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    fetchProviders();
  }, [refreshKey]);

  useEffect(() => {
    if (updatedProvider) {
      setProviders((prevProviders) =>
        prevProviders.map((provider) =>
          provider.id === updatedProvider.id ? updatedProvider : provider
        )
      );
    }
  }, [updatedProvider]);

  const fetchProviders = async () => {
    try {
      setLoading(true);
      const data = await getAllLLMProviders();
      setProviders(data);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch LLM providers"
      );
      toast.error("Failed to fetch LLM providers.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteClick = (provider: LLMProvider) => {
    setProviderToDelete(provider);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!providerToDelete) return;

    try {
      setIsDeleting(true);
      await deleteLLMProvider(providerToDelete.id);
      toast.success("LLM provider deleted successfully.");
      queryClient.invalidateQueries({ queryKey: ["llmProviders"] });
      setProviders((prev) => prev.filter((p) => p.id !== providerToDelete.id));
    } catch (error) {
      toast.error("Failed to delete LLM provider.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setProviderToDelete(null);
    }
  };

  const filteredProviders = providers.filter((p) => {
    const name = p.name.toLowerCase();
    const type = p.llm_model_provider.toLowerCase();
    const model = p.llm_model.toLowerCase();
    return (
      name.includes(searchQuery.toLowerCase()) ||
      type.includes(searchQuery.toLowerCase()) ||
      model.includes(searchQuery.toLowerCase())
    );
  });

  const getConnectionBadge = (provider: LLMProvider) => {
    const status = provider.connection_status?.status ?? 'Untested';

    if (status === 'Connected') {
      return (
        <Badge variant="success">
          <CheckCircle className="w-3 h-3 mr-1" />
          Connected
        </Badge>
      );
    }

    if (status === 'Error') {
      return (
        <Badge variant="destructive">
          <AlertCircle className="w-3 h-3 mr-1" />
          Error
        </Badge>
      );
    }

    return (
      <Badge variant="outline">
        <HelpCircle className="w-3 h-3 mr-1" />
        Untested
      </Badge>
    );
  };

  const headers = ['Name', 'Type', 'Model', 'Status', 'Connection', 'Actions'];

  const renderRow = (provider: LLMProvider) => (
    <TableRow key={provider.id}>
      <TableCell className="font-medium break-all">{provider.name}</TableCell>
      <TableCell className="truncate">{provider.llm_model_provider}</TableCell>
      <TableCell className="truncate">{provider.llm_model}</TableCell>
      <TableCell className="overflow-hidden whitespace-nowrap text-clip">
        <Badge variant={provider.is_active ? 'default' : 'secondary'}>
          {provider.is_active ? 'Active' : 'Inactive'}
        </Badge>
      </TableCell>
      <TableCell className="overflow-hidden whitespace-nowrap text-clip">{getConnectionBadge(provider)}</TableCell>
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
        data={filteredProviders}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        headers={headers}
        renderRow={renderRow}
        emptyMessage="No LLM Providers found"
        searchEmptyMessage="No LLM Providers matching your search"
      />

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isInProgress={isDeleting}
        itemName={providerToDelete?.name || ""}
        description={`This action cannot be undone. This will permanently delete the provider "${providerToDelete?.name}".`}
      />
    </>
  );
}
