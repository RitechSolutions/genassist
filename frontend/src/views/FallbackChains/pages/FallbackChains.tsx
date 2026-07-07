import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { FallbackChainCard } from "../components/FallbackChainCard";
import { FallbackChainDialog } from "../components/FallbackChainDialog";
import { FallbackChain } from "@/interfaces/fallbackChain.interface";

export default function FallbackChains() {
  const [searchQuery, setSearchQuery] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [chainToEdit, setChainToEdit] = useState<FallbackChain | null>(null);

  const handleChainSaved = () => {
    setRefreshKey((k) => k + 1);
  };

  const handleCreate = () => {
    setDialogMode("create");
    setChainToEdit(null);
    setIsDialogOpen(true);
  };

  const handleEdit = (chain: FallbackChain) => {
    setDialogMode("edit");
    setChainToEdit(chain);
    setIsDialogOpen(true);
  };

  return (
    <PageLayout>
      <PageHeader
        title="Fallback Chains"
        subtitle="Configure ordered LLM provider failover with retry policies"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search chains..."
        actionButtonText="Add New Chain"
        onActionClick={handleCreate}
      />

      <FallbackChainCard
        searchQuery={searchQuery}
        refreshKey={refreshKey}
        onEdit={handleEdit}
      />

      <FallbackChainDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onChainSaved={handleChainSaved}
        chainToEdit={chainToEdit}
        mode={dialogMode}
      />
    </PageLayout>
  );
}
