import { useEffect, useState } from "react";
import { getAllLLMProviders, deleteLLMProvider } from "@/services/llmProviders";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { LLMProviderCard } from "../components/LLMProviderCard";
import { LLMProviderDialog } from "../components/LLMProviderDialog";
import { LlmCostRatesDialog } from "../components/LlmCostRatesDialog";
import { LlmModelCatalogDialog } from "../components/LlmModelCatalogDialog";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { Brain, Coins, MoreVertical } from "lucide-react";
import { Button } from "@/components/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/dropdown-menu";
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
  const [costRatesOpen, setCostRatesOpen] = useState(false);
  const [modelCatalogOpen, setModelCatalogOpen] = useState(false);

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
        trailingActions={
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="rounded-full shrink-0 self-end sm:self-auto"
                aria-label="More actions"
              >
                <MoreVertical className="w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={() => setCostRatesOpen(true)}>
                <Coins className="w-4 h-4 mr-2 text-primary" />
                Manage costs
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => setModelCatalogOpen(true)}>
                <Brain className="w-4 h-4 mr-2 text-primary" />
                Manage models
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        }
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

      <LlmCostRatesDialog open={costRatesOpen} onOpenChange={setCostRatesOpen} />

      <LlmModelCatalogDialog
        open={modelCatalogOpen}
        onOpenChange={setModelCatalogOpen}
      />
    </PageLayout>
  );
}
