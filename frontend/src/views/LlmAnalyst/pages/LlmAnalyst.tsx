import { useEffect, useState } from "react";
import { getAllLLMAnalysts, deleteLLMAnalyst } from "@/services/llmAnalyst";
import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { LLMAnalystCard } from "@/views/LlmAnalyst/components/LLMAnalystCard";
import { useIsMobile } from "@/hooks/useMobile";
import { Search, Plus } from "lucide-react";
import { Button } from "@/components/button";
import { LLMAnalystDialog } from "../components/LLMAnalystDialog";
import { LLMAnalyst } from "@/interfaces/llmAnalyst.interface";
import toast from "react-hot-toast";

export default function LLMAnalysts() {
  const isMobile = useIsMobile();
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [llmAnalystToEdit, setLlmAnalystToEdit] = useState<LLMAnalyst | null>(null);

  const [llmAnalysts, setLlmAnalysts] = useState<LLMAnalyst[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  
  useEffect(() => {
    const fetchLLMAnalysts = async () => {
      try {
        setIsLoading(true);
        const data = await getAllLLMAnalysts();
        setLlmAnalysts(data);
      } catch (error) {
        console.error("Failed to fetch LLM analysts:", error);
      } finally {
        setIsLoading(false);
      }
    };
  
    fetchLLMAnalysts();
  }, [refreshKey]);

  const handleLLMAnalystSaved = () => {
    setRefreshKey((prevKey) => prevKey + 1);
  };

  const handleCreateLLMAnalyst = () => {
    setDialogMode("create");
    setLlmAnalystToEdit(null);
    setIsDialogOpen(true);
  };

  const handleEditLLMAnalyst = (llmAnalyst: LLMAnalyst) => {
    setDialogMode("edit");
    setLlmAnalystToEdit(llmAnalyst);
    setIsDialogOpen(true);
  };

  const handleDeleteLLMAnalyst = async (id: string) => {
    try {
      await deleteLLMAnalyst(id);
      toast.success("LLM Analyst deleted");
      setRefreshKey((prev) => prev + 1);
    } catch (error) {
      toast.error("Failed to delete LLM Analyst");
    }
  };
  
  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
      {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100">
          <div className="flex-1 p-8">
            <div className="max-w-7xl mx-auto space-y-6">
              <div className="flex justify-between items-start">
                <div>
                  <h1 className="text-3xl font-bold mb-2 animate-fade-down">
                    LLM Analysts
                  </h1>
                  <p className="text-muted-foreground animate-fade-up">
                    View and manage LLM analysts
                  </p>
                </div>
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <input
                      type="text"
                      placeholder="Search LLM analysts..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <Button
                    className="flex items-center gap-2"
                    onClick={handleCreateLLMAnalyst}
                  >
                    <Plus className="w-4 h-4" />
                    Add New LLM Analyst
                  </Button>
                </div>
              </div>
              <LLMAnalystCard
                searchQuery={searchQuery}
                analysts={llmAnalysts}
                onEdit={handleEditLLMAnalyst}
                onDelete={handleDeleteLLMAnalyst}
              />
            </div>
          </div>
        </main>
      </div>
      <LLMAnalystDialog
            isOpen={isDialogOpen}
            onOpenChange={setIsDialogOpen}
            onAnalystSaved={handleLLMAnalystSaved}
            analystToEdit={llmAnalystToEdit}
            mode={dialogMode}
      />
    </SidebarProvider>
  );
}
