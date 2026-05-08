import { useEffect, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { TableCell, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { AudioProvider } from "@/interfaces/audioProvider.interface";
import { getAllAudioProviders, deleteAudioProvider } from "@/services/audioProviders";
import { toast } from "react-hot-toast";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle, AlertCircle, HelpCircle } from "lucide-react";

interface AudioProviderCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEdit: (provider: AudioProvider) => void;
  updatedProvider?: AudioProvider | null;
}

export function AudioProviderCard({
  searchQuery,
  refreshKey = 0,
  onEdit,
  updatedProvider = null,
}: AudioProviderCardProps) {
  const [providers, setProviders] = useState<AudioProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [providerToDelete, setProviderToDelete] = useState<AudioProvider | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    fetchProviders();
  }, [refreshKey]);

  useEffect(() => {
    if (updatedProvider) {
      setProviders((prev) =>
        prev.map((p) => (p.id === updatedProvider.id ? updatedProvider : p))
      );
    }
  }, [updatedProvider]);

  const fetchProviders = async () => {
    try {
      setLoading(true);
      const data = await getAllAudioProviders();
      setProviders(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch audio providers");
      toast.error("Failed to fetch audio providers.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteClick = (provider: AudioProvider) => {
    setProviderToDelete(provider);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!providerToDelete) return;
    try {
      setIsDeleting(true);
      await deleteAudioProvider(providerToDelete.id);
      toast.success("Audio provider deleted successfully.");
      queryClient.invalidateQueries({ queryKey: ["audioProviders"] });
      setProviders((prev) => prev.filter((p) => p.id !== providerToDelete.id));
    } catch {
      toast.error("Failed to delete audio provider.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setProviderToDelete(null);
    }
  };

  const filteredProviders = providers.filter((p) => {
    const q = searchQuery.toLowerCase();
    return (
      p.name.toLowerCase().includes(q) ||
      p.provider_type.toLowerCase().includes(q) ||
      p.capability.toLowerCase().includes(q)
    );
  });

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

  const headers = ["Name", "Type", "Capability", "Status", "Connection", "Actions"];

  const renderRow = (provider: AudioProvider) => (
    <TableRow key={provider.id}>
      <TableCell className="font-medium break-all">{provider.name}</TableCell>
      <TableCell className="truncate">{provider.provider_type}</TableCell>
      <TableCell>{getCapabilityBadge(provider.capability)}</TableCell>
      <TableCell className="overflow-hidden whitespace-nowrap text-clip">
        <Badge variant={provider.is_active ? "default" : "secondary"}>
          {provider.is_active ? "Active" : "Inactive"}
        </Badge>
      </TableCell>
      <TableCell className="overflow-hidden whitespace-nowrap text-clip">
        {getConnectionBadge(provider)}
      </TableCell>
      <TableCell>
        <ActionButtons
          onEdit={() => onEdit(provider)}
          onDelete={() => handleDeleteClick(provider)}
          editTitle="Edit"
          deleteTitle="Delete"
        />
      </TableCell>
    </TableRow>
  );

  return (
    <>
      <DataTable
        data={filteredProviders}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        headers={headers}
        renderRow={renderRow}
        emptyMessage="No Audio Providers found"
        searchEmptyMessage="No Audio Providers matching your search"
      />

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isInProgress={isDeleting}
        itemName={providerToDelete?.name || ""}
        description={`This action cannot be undone. This will permanently delete the provider "${providerToDelete?.name}".`}
      />
    </>
  );
}
