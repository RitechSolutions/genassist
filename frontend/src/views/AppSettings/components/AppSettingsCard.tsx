import { useState } from "react";
import { DataTable } from "@/components/DataTable";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { TableCell, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { toast } from "react-hot-toast";
import { formatDate } from "@/helpers/utils";

interface AppSettingsCardProps {
  appSettings: AppSetting[];
  searchQuery: string;
  refreshKey: number;
  onEditSetting?: (setting: AppSetting) => void;
  onDeleteSetting?: (id: string) => Promise<void>;
}

export function AppSettingsCard({
  searchQuery,
  appSettings,
  onEditSetting,
  onDeleteSetting,
}: AppSettingsCardProps) {
  const [settingToDelete, setSettingToDelete] = useState<AppSetting | null>(
    null
  );
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const filteredSettings = appSettings.filter((setting) => {
    const name = setting.name?.toLowerCase() || "";
    const type = setting.type?.toLowerCase() || "";
    const description = setting.description?.toLowerCase() || "";

    return (
      name.includes(searchQuery.toLowerCase()) ||
      type.includes(searchQuery.toLowerCase()) ||
      description.includes(searchQuery.toLowerCase())
    );
  });

  const handleDeleteClick = (setting: AppSetting) => {
    setSettingToDelete(setting);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!settingToDelete?.id || !onDeleteSetting) return;

    try {
      setIsDeleting(true);
      await onDeleteSetting(settingToDelete.id);
      toast.success("App setting deleted successfully.");
    } catch (error) {
      toast.error("Failed to delete app setting.");
    } finally {
      setIsDeleting(false);
      setSettingToDelete(null);
      setIsDeleteDialogOpen(false);
    }
  };

  const headers = ["Name", "Type", "Values", "Status", "Created", "Actions"];

  const renderRow = (setting: AppSetting) => (
    <TableRow key={setting.id}>
      <TableCell className="font-medium break-all">{setting.name}</TableCell>
      <TableCell className="truncate">{setting.type}</TableCell>
      <TableCell>
        <div className="flex flex-col gap-1 max-w-md">
          {Object.entries(setting.values || {}).map(([key, value]) => (
            <div key={key} className="text-sm">
              <span className="font-medium text-gray-600">{key}:</span>{" "}
              <span className="font-mono text-xs">
                {value && value.length > 0 ? "••••••••" : "—"}
              </span>
            </div>
          ))}
          {Object.keys(setting.values || {}).length === 0 && (
            <span className="text-gray-400">—</span>
          )}
        </div>
      </TableCell>
      <TableCell className="overflow-hidden whitespace-nowrap text-clip">
        <Badge variant={setting.is_active === 1 ? "default" : "secondary"}>
          {setting.is_active === 1 ? "Active" : "Inactive"}
        </Badge>
      </TableCell>
      <TableCell className="truncate">
        {setting.created_at ? formatDate(setting.created_at) : "No date"}
      </TableCell>
      <TableCell>
        <ActionButtons
          onEdit={() => onEditSetting?.(setting)}
          onDelete={() => handleDeleteClick(setting)}
          editTitle="Edit App Setting"
          deleteTitle="Delete App Setting"
        />
      </TableCell>
    </TableRow>
  );

  return (
    <>
      <DataTable
        data={filteredSettings}
        loading={false}
        error={null}
        searchQuery={searchQuery}
        headers={headers}
        renderRow={renderRow}
        emptyMessage="No app settings found"
        searchEmptyMessage="No app settings found matching your search"
      />

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isInProgress={isDeleting}
        itemName={settingToDelete?.name || ""}
        description={`This action cannot be undone. This will permanently delete the app setting "${settingToDelete?.name}".`}
      />
    </>
  );
}
