import { useState } from "react";
import { Column } from "@/components/ui/data-table";
import { EntityTableCard } from "@/components/EntityTableCard";
import { Badge } from "@/components/badge";
import { FallbackChain } from "@/interfaces/fallbackChain.interface";
import { getAllFallbackChains, deleteFallbackChain } from "@/services/fallbackChains";
import { getAllLLMProviders } from "@/services/llmProviders";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { useQueryClient } from "@tanstack/react-query";

interface FallbackChainCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEdit: (chain: FallbackChain) => void;
}

export function FallbackChainCard({
  searchQuery,
  refreshKey = 0,
  onEdit,
}: FallbackChainCardProps) {
  const [providersById, setProvidersById] = useState<Record<string, LLMProvider>>({});
  const queryClient = useQueryClient();

  const fetchChains = async () => {
    const [chainData, providerData] = await Promise.all([
      getAllFallbackChains(),
      getAllLLMProviders(),
    ]);
    setProvidersById(Object.fromEntries(providerData.map((p) => [p.id, p])));
    return chainData;
  };

  const providerLabel = (id: string) => providersById[id]?.name ?? id;

  const timeoutLabel = (chain: FallbackChain) => {
    const def = chain.retry_policy?.timeout_seconds ?? 0;
    const hasPerProvider = Object.keys(chain.retry_policy?.provider_timeouts ?? {}).length > 0;
    const parts: string[] = [];
    if (def) parts.push(`${def}s`);
    if (hasPerProvider) parts.push("per-provider");
    return parts.length ? parts.join(" + ") : "—";
  };

  const columns: Column<FallbackChain>[] = [
    {
      header: "Name",
      key: "name",
      cell: (chain) => chain.name,
      className: "font-medium break-all",
    },
    {
      header: "Providers (priority order)",
      key: "providers",
      cell: (chain) => (chain.provider_ids ?? []).map(providerLabel).join(" → "),
      className: "truncate",
    },
    {
      header: "Retry",
      key: "retry",
      cell: (chain) =>
        `${chain.retry_policy?.retry_count ?? 0}× / ${chain.retry_policy?.backoff_seconds ?? 0}s`,
      className: "truncate",
    },
    {
      header: "Timeout",
      key: "timeout",
      cell: (chain) => timeoutLabel(chain),
      className: "truncate",
    },
    {
      header: "Status",
      key: "status",
      className: "overflow-hidden whitespace-nowrap text-clip",
      cell: (chain) => (
        <Badge variant={chain.is_active ? "default" : "secondary"}>
          {chain.is_active ? "Active" : "Inactive"}
        </Badge>
      ),
    },
  ];

  return (
    <EntityTableCard<FallbackChain>
      entityName="fallback chain"
      searchQuery={searchQuery}
      searchFields={["name"]}
      refreshKey={refreshKey}
      fetchFn={fetchChains}
      deleteFn={(chain) => deleteFallbackChain(chain.id)}
      getItemName={(chain) => chain.name}
      deleteDescription={(chain) =>
        `This action cannot be undone. This will permanently delete the chain "${chain.name}".`
      }
      onDeleted={() =>
        queryClient.invalidateQueries({ queryKey: ["fallbackChains"] })
      }
      emptyMessage="No fallback chains found"
      notFoundMessage="No fallback chains matching your search"
      columns={columns}
      rowActions={{
        onEdit,
        editTitle: "Edit",
        deleteTitle: "Delete",
      }}
    />
  );
}
