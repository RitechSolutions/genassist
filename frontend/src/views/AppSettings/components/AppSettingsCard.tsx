import { useEffect, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { ActionButtons } from "@/components/ActionButtons";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { TableCell, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { getAllAppSettings, deleteAppSetting } from "@/services/appSettings";
import { toast } from "react-hot-toast";
import { formatDate } from "@/helpers/utils";

interface AppSettingsCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditSetting: (setting: AppSetting) => void;
}

export function AppSettingsCard({ searchQuery, refreshKey = 0, onEditSetting }: AppSettingsCardProps) {
  const [settings, setSettings] = useState<AppSetting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [settingToDelete, setSettingToDelete] = useState<AppSetting | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    fetchData();
  }, [refreshKey]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const settingsData = await getAllAppSettings();
      setSettings(settingsData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch data");
      toast.error("Failed to fetch data");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteClick = (setting: AppSetting) => {
    setSettingToDelete(setting);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!settingToDelete) return;
    
    try {
      setIsDeleting(true);
      await deleteAppSetting(settingToDelete.id);
      toast.success("Setting deleted successfully");
      fetchData();
    } catch (err) {
      toast.error("Failed to delete setting");
    } finally {
      setIsDeleting(false);
      setSettingToDelete(null);
      setIsDeleteDialogOpen(false);
    }
  };

  const filteredSettings = settings.filter((setting) =>
    setting.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
    setting.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    setting.value.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const headers = ["Key", "Value", "Description", "Status", "Encrypted", "Created", "Actions"];

  const renderRow = (setting: AppSetting) => (
    <TableRow key={setting.id}>
      <TableCell className="font-medium">{setting.key}</TableCell>
      <TableCell>
        <div className="flex items-center">
          <span className="font-mono text-sm max-w-[200px] truncate">
            {setting.encrypted === 1 ? "••••••••" : setting.value}
          </span>
        </div>
      </TableCell>
      <TableCell className="max-w-[300px]">
        <span className="line-clamp-2">{setting.description}</span>
      </TableCell>
      <TableCell>
        <Badge variant={setting.is_active === 1 ? "default" : "secondary"}>
          {setting.is_active === 1 ? "Active" : "Inactive"}
        </Badge>
      </TableCell>
      <TableCell>
        {setting.encrypted === 1 ? (
          <span className="w-4 h-4 text-gray-500">Yes</span>
        ) : (
          <span className="w-4 h-4 text-gray-500">No</span>
        )}
      </TableCell>
      <TableCell>{setting.created_at ? formatDate(setting.created_at) : 'No date'}</TableCell>
      <TableCell>
        <ActionButtons
          onEdit={() => onEditSetting(setting)}
          onDelete={() => handleDeleteClick(setting)}
          editTitle="Edit Setting"
          deleteTitle="Delete Setting"
        />
      </TableCell>
    </TableRow>
  );

  return (
    <>
      <DataTable
        data={filteredSettings}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        headers={headers}
        renderRow={renderRow}
        emptyMessage="No settings found"
        searchEmptyMessage="No settings found matching your search"
      />

      <DeleteConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isDeleting={isDeleting}
        itemName={settingToDelete?.key || ""}
        description={`This will permanently delete the setting "${settingToDelete?.key}". This action cannot be undone.`}
      />
    </>
  );
} 