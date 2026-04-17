import { useRef, useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { ApiKeysCard } from "@/views/ApiKeys/components/ApiKeysCard";
import { ApiKey } from "@/interfaces/api-key.interface";
import { ApiKeyDialog } from "../components/ApiKeyDialog";
import { revokeApiKey } from "@/services/apiKeys";
import { toast } from "react-hot-toast";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";

export default function ApiKeys() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [apiKeyToEdit, setApiKeyToEdit] = useState<ApiKey | null>(null);
  const [updatedApiKey, setUpdatedApiKey] = useState<ApiKey | null>(null);
  const [apiKeyPendingDelete, setApiKeyPendingDelete] = useState<ApiKey | null>(null);
  const [isDeletingApiKey, setIsDeletingApiKey] = useState(false);
  const isDeletingApiKeyRef = useRef(false);

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

  const handleDeleteApiKey = (apiKey: ApiKey) => {
    setApiKeyPendingDelete(apiKey);
  };

  const handleConfirmDeleteApiKey = async () => {
    if (!apiKeyPendingDelete) return;

    isDeletingApiKeyRef.current = true;
    setIsDeletingApiKey(true);
    try {
      await revokeApiKey(apiKeyPendingDelete.id);
      toast.success("API key deleted successfully");
      setApiKeyPendingDelete(null);
      setRefreshKey((prevKey) => prevKey + 1);
    } catch {
      toast.error("Failed to delete API key");
    } finally {
      isDeletingApiKeyRef.current = false;
      setIsDeletingApiKey(false);
    }
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
        onApiKeyRotated={handleApiKeyUpdated}
        onDeleteApiKey={handleDeleteApiKey}
      />

      <ApiKeyDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onApiKeyCreated={handleApiKeySaved}
        onApiKeyUpdated={handleApiKeyUpdated}
        apiKeyToEdit={apiKeyToEdit}
        mode={dialogMode}
      />

      <DeleteConfirmationDialog
        open={apiKeyPendingDelete !== null}
        onOpenChange={(open) => {
          if (!open && !isDeletingApiKeyRef.current) {
            setApiKeyPendingDelete(null);
          }
        }}
        onConfirm={handleConfirmDeleteApiKey}
        isDeleting={isDeletingApiKey}
        title="Delete API key?"
        itemName={apiKeyPendingDelete?.name}
        confirmButtonText="Delete"
        loadingText="Deleting..."
      />
    </PageLayout>
  );
}
