import { useEffect, useState } from "react";
import { getAllLLMProviders, deleteLLMProvider } from "@/services/llmProviders";
import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { LLMProviderCard } from "../components/LLMProviderCard";
import { useIsMobile } from "@/hooks/useMobile";
import { Search, Plus } from "lucide-react";
import { Button } from "@/components/button";
import { LLMProviderDialog } from "../components/LLMProviderDialog";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import toast from "react-hot-toast";

export default function LLMProviders() {
  const isMobile = useIsMobile();
  const [searchQuery, setSearchQuery] = useState("");
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [providerToEdit, setProviderToEdit] = useState<LLMProvider | null>(
    null
  );

  // Fetch all providers
  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const data = await getAllLLMProviders();
        setProviders(data);
      } catch (error) {
        console.error("Failed to fetch providers:", error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [refreshKey]);

  const handleProviderSaved = () => {
    setRefreshKey((k) => k + 1);
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
      toast.success("Provider deleted");
      setRefreshKey((prev) => prev + 1);
    } catch (error) {
      console.error("Failed to delete provider:", error);
      toast.error(
        "This provider is in use. First delete LLM Analyst(s) using it."
      );
    }
  };

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100">
          <div className="flex-1 p-8">
            <div className="max-w-2xl xl:max-w-7xl mx-auto space-y-6">
              <div className="flex justify-between items-start">
                <div>
                  <h1 className="text-3xl font-bold mb-2 animate-fade-down">
                    LLM Providers
                  </h1>
                  <p className="text-muted-foreground animate-fade-up">
                    View and manage LLM providers
                  </p>
                </div>
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 text-gray-400 w-5 h-5 transform -translate-y-1/2" />
                    <input
                      type="text"
                      placeholder="Search providers..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <Button
                    onClick={handleCreate}
                    className="flex items-center gap-2"
                  >
                    <Plus className="w-4 h-4" />
                    Add New Provider
                  </Button>
                </div>
              </div>
              <LLMProviderCard
                providers={providers}
                searchQuery={searchQuery}
                loading={isLoading}
                onEdit={handleEdit}
                onDelete={handleDelete}
              />
            </div>
          </div>
        </main>
      </div>

      <LLMProviderDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onProviderSaved={handleProviderSaved}
        providerToEdit={providerToEdit}
        mode={dialogMode}
      />
    </SidebarProvider>
  );
}
