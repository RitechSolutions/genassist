import { useEffect, useState } from "react";
import { getAllLLMAnalysts, deleteLLMAnalyst } from "@/services/llmAnalyst";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { LLMAnalystCard } from "@/views/LlmAnalyst/components/LLMAnalystCard";
import { LLMAnalystDialog } from "../components/LLMAnalystDialog";
import { LLMAnalyst } from "@/interfaces/llmAnalyst.interface";
import toast from "react-hot-toast";

export default function LLMAnalysts() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [llmAnalystToEdit, setLlmAnalystToEdit] = useState<LLMAnalyst | null>(
    null
  );

  const [llmAnalysts, setLlmAnalysts] = useState<LLMAnalyst[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchLLMAnalysts = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const data = await getAllLLMAnalysts();
        setLlmAnalysts(data);
      } catch (error) {
        setError("We couldn't load your LLM analysts. Please try again.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchLLMAnalysts();
  }, [refreshKey]);

  const handleRetry = () => setRefreshKey((prevKey) => prevKey + 1);

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
      //toast.success("LLM analyst deleted successfully.");
      setRefreshKey((prev) => prev + 1);
    } catch (error) {
      toast.error("Failed to delete LLM analyst.");
    }
  };

  return (
    <PageLayout>
      <PageHeader
        title="LLM Analysts"
        subtitle="View and manage LLM analysts"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search LLM analysts..."
        actionButtonText="Add New LLM Analyst"
        onActionClick={handleCreateLLMAnalyst}
      />

      <LLMAnalystCard
        searchQuery={searchQuery}
        analysts={llmAnalysts}
        loading={isLoading}
        error={error}
        onRetry={handleRetry}
        onCreate={handleCreateLLMAnalyst}
        onEdit={handleEditLLMAnalyst}
        onDelete={handleDeleteLLMAnalyst}
      />

      <LLMAnalystDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onAnalystSaved={handleLLMAnalystSaved}
        analystToEdit={llmAnalystToEdit}
        mode={dialogMode}
      />
    </PageLayout>
  );
}
