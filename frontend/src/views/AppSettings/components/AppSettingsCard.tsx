import { useState, useMemo } from "react";
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

  // Define display item interface
  interface DisplayItem {
    type: 'setting';
    data: AppSetting;
    groupName?: string;
    isGrouped?: boolean;
  }

  // Group settings by type and create a flattened structure for rendering
  const displayData = useMemo<DisplayItem[]>(() => {
    const typeCount: Record<string, number> = {};
    
    // Count occurrences of each type
    filteredSettings.forEach((setting) => {
      const type = setting.type || "Unknown";
      typeCount[type] = (typeCount[type] || 0) + 1;
    });

    // Group settings by type
    const groups: Record<string, AppSetting[]> = {};
    filteredSettings.forEach((setting) => {
      const type = setting.type || "Unknown";
      if (!groups[type]) {
        groups[type] = [];
      }
      groups[type].push(setting);
    });

    // Create flattened display data with group markers
    const flatData: DisplayItem[] = [];
    Object.entries(groups).forEach(([type, settings]) => {
      const shouldGroup = typeCount[type] >= 2;
      
      if (shouldGroup) {
        settings.forEach((setting, index) => {
          flatData.push({
            type: 'setting',
            data: setting,
            groupName: index === 0 ? type : undefined,
            isGrouped: true,
          });
        });
      } else {
        settings.forEach((setting) => {
          flatData.push({
            type: 'setting',
            data: setting,
            isGrouped: false,
          });
        });
      }
    });

    return flatData;
  }, [filteredSettings]);

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

  const renderRow = (item: DisplayItem) => {
    const { data: setting, groupName, isGrouped } = item;
    
    const rows: JSX.Element[] = [];
    
    // Add group header if this is the first item in a group
    if (groupName) {
      rows.push(
        <TableRow key={`group-${groupName}`} className="bg-gray-50/50 hover:bg-gray-50/50 border-t-2 border-gray-200">
          <TableCell colSpan={6} className="font-semibold text-gray-700 py-3">
            {groupName}
          </TableCell>
        </TableRow>
      );
    }
    
    // Add the setting row
    rows.push(
      <TableRow key={setting.id}>
        <TableCell className="font-medium break-all">{setting.name}</TableCell>
        <TableCell className="truncate">{isGrouped ? "" : setting.type}</TableCell>
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
    
    return rows;
  };

  return (
    <>
      <DataTable
        data={displayData}
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
