import { useEffect, useState } from "react";
import { DataTable, Column } from "@/components/ui/data-table";
import { LIST_PAGE_SIZE } from "@/constants/pagination";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge } from "@/components/badge";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { getAllLLMProviders, deleteLLMProvider } from "@/services/llmProviders";
import { toast } from "react-hot-toast";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle, AlertCircle, HelpCircle } from 'lucide-react';
import { AxiosError } from "axios";

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
      const axiosError = error as AxiosError<{ error?: string }>;
      toast.error(
        axiosError.response?.data?.error ?? "Failed to delete LLM provider."
      );
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

  const columns: Column<LLMProvider>[] = [
    {
      header: "Name",
      key: "name",
      cell: (provider) => provider.name,
      className: "font-medium break-all",
    },
    {
      header: "Type",
      key: "llm_model_provider",
      cell: (provider) => provider.llm_model_provider,
      className: "truncate",
    },
    {
      header: "Model",
      key: "llm_model",
      cell: (provider) => provider.llm_model,
      className: "truncate",
    },
    {
      header: "Status",
      key: "status",
      className: "overflow-hidden whitespace-nowrap text-clip",
      cell: (provider) => (
        <Badge variant={provider.is_active ? "default" : "secondary"}>
          {provider.is_active ? "Active" : "Inactive"}
        </Badge>
      ),
    },
    {
      header: "Connection",
      key: "connection",
      className: "overflow-hidden whitespace-nowrap text-clip",
      cell: (provider) => getConnectionBadge(provider),
    },
    {
      header: "Actions",
      key: "actions",
      cell: (provider) => (
        <ActionButtons
          onEdit={() => onEdit(provider)}
          onDelete={() => handleDeleteClick(provider)}
          editTitle="Edit"
          deleteTitle="Delete"
        />
      ),
    },
  ];

  return (
    <>
      <DataTable
        data={filteredProviders}
        columns={columns}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        pageSize={LIST_PAGE_SIZE}
        emptyMessage="No LLM Providers found"
        notFoundMessage="No LLM Providers matching your search"
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
