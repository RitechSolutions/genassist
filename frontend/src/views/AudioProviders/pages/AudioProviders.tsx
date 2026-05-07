import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { AudioProviderCard } from "../components/AudioProviderCard";
import { AudioProviderDialog } from "../components/AudioProviderDialog";
import { AudioProvider } from "@/interfaces/audioProvider.interface";

export default function AudioProviders() {
  const [searchQuery, setSearchQuery] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [providerToEdit, setProviderToEdit] = useState<AudioProvider | null>(null);
  const [updatedProvider, setUpdatedProvider] = useState<AudioProvider | null>(null);

  const handleProviderSaved = () => {
    setRefreshKey((k) => k + 1);
  };

  const handleProviderUpdated = (provider: AudioProvider) => {
    setUpdatedProvider(provider);
  };

  const handleCreate = () => {
    setDialogMode("create");
    setProviderToEdit(null);
    setIsDialogOpen(true);
  };

  const handleEdit = (prov: AudioProvider) => {
    setDialogMode("edit");
    setProviderToEdit(prov);
    setIsDialogOpen(true);
  };

  return (
    <PageLayout>
      <PageHeader
        title="Audio Providers"
        subtitle="Manage TTS and STT audio providers"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search providers..."
        actionButtonText="Add Audio Provider"
        onActionClick={handleCreate}
      />

      <AudioProviderCard
        searchQuery={searchQuery}
        refreshKey={refreshKey}
        onEdit={handleEdit}
        updatedProvider={updatedProvider}
      />

      <AudioProviderDialog
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
