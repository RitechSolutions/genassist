import { Column } from "@/components/ui/data-table";
import { EntityTableCard } from "@/components/EntityTableCard";
import { Badge } from "@/components/badge";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { getAllLLMProviders, deleteLLMProvider } from "@/services/llmProviders";
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
  const queryClient = useQueryClient();

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
  ];

  return (
    <EntityTableCard<LLMProvider>
      searchQuery={searchQuery}
      searchFields={["name", "llm_model_provider", "llm_model"]}
      refreshKey={refreshKey}
      updatedItem={updatedProvider}
      fetchFn={getAllLLMProviders}
      fetchErrorMessage="Failed to fetch LLM providers."
      deleteFn={(provider) => deleteLLMProvider(provider.id)}
      getItemName={(provider) => provider.name}
      deleteDescription={(provider) =>
        `This action cannot be undone. This will permanently delete the provider "${provider.name}".`
      }
      deleteSuccessMessage="LLM provider deleted successfully."
      deleteErrorMessage="Failed to delete LLM provider."
      onDeleted={() =>
        queryClient.invalidateQueries({ queryKey: ["llmProviders"] })
      }
      emptyMessage="No LLM Providers found"
      notFoundMessage="No LLM Providers matching your search"
      columns={columns}
      rowActions={{
        onEdit,
        editTitle: "Edit",
        deleteTitle: "Delete",
      }}
    />
  );
}
