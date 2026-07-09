import { useEffect, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { TableCell, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { FallbackChain } from "@/interfaces/fallbackChain.interface";
import { getAllFallbackChains, deleteFallbackChain } from "@/services/fallbackChains";
import { getAllLLMProviders } from "@/services/llmProviders";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { toast } from "react-hot-toast";
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
  const [chains, setChains] = useState<FallbackChain[]>([]);
  const [providersById, setProvidersById] = useState<Record<string, LLMProvider>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chainToDelete, setChainToDelete] = useState<FallbackChain | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    fetchChains();
  }, [refreshKey]);

  const fetchChains = async () => {
    try {
      setLoading(true);
      const [chainData, providerData] = await Promise.all([
        getAllFallbackChains(),
        getAllLLMProviders(),
      ]);
      setChains(chainData);
      setProvidersById(
        Object.fromEntries(providerData.map((p) => [p.id, p]))
      );
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch fallback chains"
      );
      toast.error("Failed to fetch fallback chains.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteClick = (chain: FallbackChain) => {
    setChainToDelete(chain);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!chainToDelete) return;
    try {
      setIsDeleting(true);
      await deleteFallbackChain(chainToDelete.id);
      toast.success("Fallback chain deleted successfully.");
      queryClient.invalidateQueries({ queryKey: ["fallbackChains"] });
      setChains((prev) => prev.filter((c) => c.id !== chainToDelete.id));
    } catch {
      toast.error("Failed to delete fallback chain.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setChainToDelete(null);
    }
  };

  const providerLabel = (id: string) => providersById[id]?.name ?? id;

  const filteredChains = chains.filter((c) =>
    (c.name ?? "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  const headers = ["Name", "Providers (priority order)", "Retry", "Timeout", "Status", "Actions"];

  const timeoutLabel = (chain: FallbackChain) => {
    const def = chain.retry_policy?.timeout_seconds ?? 0;
    const hasPerProvider = Object.keys(chain.retry_policy?.provider_timeouts ?? {}).length > 0;
    const parts: string[] = [];
    if (def) parts.push(`${def}s`);
    if (hasPerProvider) parts.push("per-provider");
    return parts.length ? parts.join(" + ") : "—";
  };

  const renderRow = (chain: FallbackChain) => (
    <TableRow key={chain.id}>
      <TableCell className="font-medium break-all">{chain.name}</TableCell>
      <TableCell className="truncate">
        {(chain.provider_ids ?? []).map(providerLabel).join(" → ")}
      </TableCell>
      <TableCell className="truncate">
        {chain.retry_policy?.retry_count ?? 0}× / {chain.retry_policy?.backoff_seconds ?? 0}s
      </TableCell>
      <TableCell className="truncate">{timeoutLabel(chain)}</TableCell>
      <TableCell className="overflow-hidden whitespace-nowrap text-clip">
        <Badge variant={chain.is_active ? "default" : "secondary"}>
          {chain.is_active ? "Active" : "Inactive"}
        </Badge>
      </TableCell>
      <TableCell>
        <ActionButtons
          onEdit={() => onEdit(chain)}
          onDelete={() => handleDeleteClick(chain)}
          editTitle="Edit"
          deleteTitle="Delete"
        />
      </TableCell>
    </TableRow>
  );

  return (
    <>
      <DataTable
        data={filteredChains}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        headers={headers}
        renderRow={renderRow}
        emptyMessage="No fallback chains found"
        searchEmptyMessage="No fallback chains matching your search"
      />

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isInProgress={isDeleting}
        itemName={chainToDelete?.name || ""}
        description={`This action cannot be undone. This will permanently delete the chain "${chainToDelete?.name}".`}
      />
    </>
  );
}
