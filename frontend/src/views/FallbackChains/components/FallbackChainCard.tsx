import { useState } from "react";
import { Column } from "@/components/ui/data-table";
import { EntityTableCard } from "@/components/EntityTableCard";
import { Badge } from "@/components/badge";
import { FallbackChain } from "@/interfaces/fallbackChain.interface";
import { getAllFallbackChains, deleteFallbackChain } from "@/services/fallbackChains";
import { getAllLLMProviders } from "@/services/llmProviders";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { useQueryClient } from "@tanstack/react-query";
import { Waypoints } from "lucide-react";
import { Button } from "@/components/button";

interface FallbackChainCardProps {
  searchQuery: string;
  refreshKey?: number;
  onCreate?: () => void;
  onEdit: (chain: FallbackChain) => void;
}

export function FallbackChainCard({
  searchQuery,
  refreshKey = 0,
  onCreate,
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
      emptyState={{
        icon: <Waypoints className="h-12 w-12 text-muted-foreground" />,
        title: "No fallback chains yet",
        description:
          "Fallback chains route requests across providers so a failure automatically retries the next one. Add one to improve resilience.",
        searchTitle: "No matching fallback chains",
        searchDescription:
          "No fallback chains match your search. Try a different name.",
        action: onCreate ? (
          <Button className="rounded-full" onClick={onCreate}>
            Create your first fallback chain
          </Button>
        ) : undefined,
      }}
      columns={columns}
      rowActions={{
        onEdit,
        editTitle: "Edit",
        deleteTitle: "Delete",
      }}
    />
  );
}
