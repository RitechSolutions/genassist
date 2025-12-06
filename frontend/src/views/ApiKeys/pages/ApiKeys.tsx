import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { ApiKeysCard } from "@/views/ApiKeys/components/ApiKeysCard";
import { ApiKey } from "@/interfaces/api-key.interface";
import { ApiKeyDialog } from "../components/ApiKeyDialog";

export default function ApiKeys() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [apiKeyToEdit, setApiKeyToEdit] = useState<ApiKey | null>(null);
  const [updatedApiKey, setUpdatedApiKey] = useState<ApiKey | null>(null);

  const handleApiKeySaved = () => {
    setRefreshKey((prevKey) => prevKey + 1);
  };

  const handleApiKeyUpdated = (apiKey: ApiKey) => {
    setUpdatedApiKey(apiKey);
  };

  const handleCreateApiKey = () => {
    setDialogMode("create");
    setApiKeyToEdit(null);
    setIsDialogOpen(true);
  };

  const handleEditApiKey = (apiKey: ApiKey) => {
    setDialogMode("edit");
    setApiKeyToEdit(apiKey);
    setIsDialogOpen(true);
  };

  return (
    <PageLayout>
      <PageHeader
        title="API Keys"
        subtitle="View and manage API keys"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search API keys..."
        actionButtonText="Generate New API Key"
        onActionClick={handleCreateApiKey}
      />

      <ApiKeysCard
        searchQuery={searchQuery}
        refreshKey={refreshKey}
        onEditApiKey={handleEditApiKey}
        updatedApiKey={updatedApiKey}
      />

      <ApiKeyDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onApiKeyCreated={handleApiKeySaved}
        onApiKeyUpdated={handleApiKeyUpdated}
        apiKeyToEdit={apiKeyToEdit}
        mode={dialogMode}
      />
    </PageLayout>
  );
}
