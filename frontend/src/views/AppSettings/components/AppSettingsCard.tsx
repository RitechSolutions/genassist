import { useState } from "react";
import { DataTable, Column } from "@/components/ui/data-table";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge } from "@/components/badge";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { toast } from "react-hot-toast";
import { formatDate } from "@/helpers/utils";

interface AppSettingsCardProps {
  appSettings: AppSetting[];
  searchQuery: string;
  refreshKey: number;
  loading?: boolean;
  onEditSetting?: (setting: AppSetting) => void;
  onDeleteSetting?: (id: string) => Promise<void>;
}

export function AppSettingsCard({
  searchQuery,
  appSettings,
  loading = false,
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

  // Count settings per type so types with 2+ settings render under a group header.
  const typeCounts = filteredSettings.reduce<Record<string, number>>(
    (acc, setting) => {
      const type = setting.type || "Unknown";
      acc[type] = (acc[type] || 0) + 1;
      return acc;
    },
    {}
  );
  const isGroupedType = (type: string) => (typeCounts[type] || 0) >= 2;

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

  const columns: Column<AppSetting>[] = [
    {
      header: "Name",
      key: "name",
      cell: (setting) => setting.name,
      className: "font-medium break-all",
    },
    {
      header: "Type",
      key: "type",
      className: "truncate",
      // Blank for grouped types (shown in the group header); inline otherwise.
      cell: (setting) => (isGroupedType(setting.type || "Unknown") ? "" : setting.type),
    },
    {
      header: "Values",
      key: "values",
      cell: (setting) => (
        <div className="flex flex-col gap-1 max-w-md">
          {Object.entries(setting.values || {}).map(([key, value]) => (
            <div key={key} className="text-sm">
              <span className="font-medium text-muted-foreground">{key}:</span>{" "}
              <span className="font-mono text-xs">
                {String(value).length > 0 ? "••••••••" : "—"}
              </span>
            </div>
          ))}
          {Object.keys(setting.values || {}).length === 0 && (
            <span className="text-muted-foreground">—</span>
          )}
        </div>
      ),
    },
    {
      header: "Status",
      key: "status",
      className: "overflow-hidden whitespace-nowrap text-clip",
      cell: (setting) => (
        <Badge variant={setting.is_active === 1 ? "default" : "secondary"}>
          {setting.is_active === 1 ? "Active" : "Inactive"}
        </Badge>
      ),
    },
    {
      header: "Created",
      key: "created_at",
      className: "truncate",
      cell: (setting) =>
        setting.created_at ? formatDate(setting.created_at) : "No date",
    },
    {
      header: "Actions",
      key: "actions",
      cell: (setting) => (
        <ActionButtons
          onEdit={() => onEditSetting?.(setting)}
          onDelete={() => handleDeleteClick(setting)}
          editTitle="Edit App Setting"
          deleteTitle="Delete App Setting"
        />
      ),
    },
  ];

  return (
    <>
      <DataTable
        data={filteredSettings}
        columns={columns}
        loading={loading}
        error={null}
        searchQuery={searchQuery}
        groupBy={(setting) => setting.type || "Unknown"}
        renderGroupHeader={(type, items) => (items.length >= 2 ? type : null)}
        emptyMessage="No app settings found"
        notFoundMessage="No app settings found matching your search"
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
