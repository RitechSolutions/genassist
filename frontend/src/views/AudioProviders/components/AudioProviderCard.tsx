import { Column } from "@/components/ui/data-table";
import { EntityTableCard } from "@/components/EntityTableCard";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { AudioProvider } from "@/interfaces/audioProvider.interface";
import { getAllAudioProviders, deleteAudioProvider } from "@/services/audioProviders";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle, AlertCircle, HelpCircle, Plus, Volume2 } from "lucide-react";

interface AudioProviderCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEdit: (provider: AudioProvider) => void;
  onCreate: () => void;
  updatedProvider?: AudioProvider | null;
}

export function AudioProviderCard({
  searchQuery,
  refreshKey = 0,
  onEdit,
  onCreate,
  updatedProvider = null,
}: AudioProviderCardProps) {
  const queryClient = useQueryClient();

  const getConnectionBadge = (provider: AudioProvider) => {
    const status = provider.connection_status?.status ?? "Untested";
    if (status === "Connected") {
      return (
        <Badge variant="success">
          <CheckCircle className="w-3 h-3 mr-1" />
          Connected
        </Badge>
      );
    }
    if (status === "Error") {
      return (
        <Badge variant="destructive">
          <AlertCircle className="w-3 h-3 mr-1" />
          Error
        </Badge>
      );
    }
    return (
      <Badge variant="outline">
        <HelpCircle className="w-3 h-3 mr-1" />
        Untested
      </Badge>
    );
  };

  const getCapabilityBadge = (capability: string) => {
    const labels: Record<string, string> = { tts: "TTS", stt: "STT", both: "TTS + STT" };
    return <Badge variant="secondary">{labels[capability] || capability}</Badge>;
  };

  const columns: Column<AudioProvider>[] = [
    {
      header: "Name",
      key: "name",
      cell: (provider) => provider.name,
      className: "font-medium break-all",
    },
    {
      header: "Type",
      key: "provider_type",
      cell: (provider) => provider.provider_type,
      className: "truncate",
    },
    {
      header: "Capability",
      key: "capability",
      cell: (provider) => getCapabilityBadge(provider.capability),
    },
    {
      header: "Status",
      key: "status",
      className: "overflow-hidden whitespace-nowrap text-clip",
      cell: (provider) => (
        <Badge variant={provider.is_active ? "default" : "secondary"}>
          {provider.is_active ? "Active" : "Inactive"}
        </Badge>
      ),
    },
    {
      header: "Connection",
      key: "connection",
      className: "overflow-hidden whitespace-nowrap text-clip",
      cell: (provider) => getConnectionBadge(provider),
    },
  ];

  return (
    <EntityTableCard<AudioProvider>
      entityName="audio provider"
      searchQuery={searchQuery}
      searchFields={["name", "provider_type", "capability"]}
      refreshKey={refreshKey}
      updatedItem={updatedProvider}
      fetchFn={getAllAudioProviders}
      deleteFn={(provider) => deleteAudioProvider(provider.id)}
      getItemName={(provider) => provider.name}
      deleteDescription={(provider) =>
        `This action cannot be undone. This will permanently delete the provider "${provider.name}".`
      }
      onDeleted={() =>
        queryClient.invalidateQueries({ queryKey: ["audioProviders"] })
      }
      emptyMessage="No Audio Providers found"
      notFoundMessage="No Audio Providers matching your search"
      emptyState={{
        icon: <Volume2 className="h-12 w-12 text-muted-foreground" />,
        title: "No Audio Providers found",
        searchTitle: "No Audio Providers matching your search",
        description:
          "Add your first audio provider to enable TTS and STT capabilities.",
        searchDescription: "Try adjusting your search query.",
        action: (
          <Button onClick={onCreate} className="rounded-full">
            <Plus className="h-4 w-4 mr-2" />
            Create your first audio provider
          </Button>
        ),
      }}
      columns={columns}
      rowActions={{
        onEdit: onEdit,
        editTitle: "Edit",
        deleteTitle: "Delete",
      }}
    />
  );
}
