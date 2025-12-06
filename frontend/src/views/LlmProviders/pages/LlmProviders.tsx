import { useEffect, useState } from "react";
import { getAllLLMProviders, deleteLLMProvider } from "@/services/llmProviders";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { LLMProviderCard } from "../components/LLMProviderCard";
import { LLMProviderDialog } from "../components/LLMProviderDialog";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import toast from "react-hot-toast";

export default function LLMProviders() {
  const [searchQuery, setSearchQuery] = useState("");
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [providerToEdit, setProviderToEdit] = useState<LLMProvider | null>(
    null
  );
  const [updatedProvider, setUpdatedProvider] = useState<LLMProvider | null>(null);

  // Fetch all providers
  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const data = await getAllLLMProviders();
        setProviders(data);
      } catch (error) {
        // ignore
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [refreshKey]);

  const handleProviderSaved = () => {
    setRefreshKey((k) => k + 1);
  };

  const handleProviderUpdated = (provider: LLMProvider) => {
    setUpdatedProvider(provider);
  };

  const handleCreate = () => {
    setDialogMode("create");
    setProviderToEdit(null);
    setIsDialogOpen(true);
  };

  const handleEdit = (prov: LLMProvider) => {
    setDialogMode("edit");
    setProviderToEdit(prov);
    setIsDialogOpen(true);
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteLLMProvider(id);
      //toast.success("LLM provider deleted successfully.");
      setRefreshKey((prev) => prev + 1);
    } catch (error) {
      toast.error(
        "Failed to delete LLM provider: LLM provider is in use by at least one LLM analyst."
      );
    }
  };

  return (
    <PageLayout>
      <PageHeader
        title="LLM Providers"
        subtitle="View and manage LLM providers"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search providers..."
        actionButtonText="Add New Provider"
        onActionClick={handleCreate}
      />

      <LLMProviderCard
        searchQuery={searchQuery}
        refreshKey={refreshKey}
        onEdit={handleEdit}
        updatedProvider={updatedProvider}
      />

      <LLMProviderDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onProviderSaved={handleProviderSaved}
        onProviderUpdated={handleProviderUpdated}
        providerToEdit={providerToEdit}
        mode={dialogMode}
      />
    </PageLayout>
  );
}
