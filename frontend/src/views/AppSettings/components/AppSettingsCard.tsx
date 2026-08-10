import { Column } from "@/components/ui/data-table";
import { EntityTableCard } from "@/components/EntityTableCard";
import { Badge } from "@/components/badge";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { formatDate } from "@/helpers/utils";

interface AppSettingsCardProps {
  appSettings: AppSetting[];
  searchQuery: string;
  refreshKey: number;
  loading?: boolean;
  onEditSetting?: (setting: AppSetting) => void;
  onDeleteSetting?: (id: string) => Promise<void>;
}

// Case-insensitive match across name/type/description (untrimmed query, matching
// the original card's search behavior). Shared between EntityTableCard's filterFn
// and the local grouping counts below so the two never diverge.
const matchesQuery = (setting: AppSetting, query: string) => {
  const q = query.toLowerCase();
  return (
    (setting.name?.toLowerCase() || "").includes(q) ||
    (setting.type?.toLowerCase() || "").includes(q) ||
    (setting.description?.toLowerCase() || "").includes(q)
  );
};

export function AppSettingsCard({
  searchQuery,
  appSettings,
  loading = false,
  onEditSetting,
  onDeleteSetting,
}: AppSettingsCardProps) {
  // Recompute the filtered set exactly as EntityTableCard does internally, so the
  // Type column's "blank when grouped" logic stays in sync with the group headers
  // (EntityTableCard does not expose its filtered rows to the columns builder).
  const trimmedQuery = searchQuery.trim();
  const filteredForGrouping =
    trimmedQuery.length === 0
      ? appSettings
      : appSettings.filter((setting) => matchesQuery(setting, searchQuery));

  // Count settings per type so types with 2+ settings render under a group header.
  const typeCounts = filteredForGrouping.reduce<Record<string, number>>(
    (acc, setting) => {
      const type = setting.type || "Unknown";
      acc[type] = (acc[type] || 0) + 1;
      return acc;
    },
    {}
  );
  const isGroupedType = (type: string) => (typeCounts[type] || 0) >= 2;

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
  ];

  return (
    <EntityTableCard<AppSetting>
      entityName="app setting"
      data={appSettings}
      loading={loading}
      searchQuery={searchQuery}
      filterFn={matchesQuery}
      deleteFn={(setting) => onDeleteSetting?.(setting.id) ?? Promise.resolve()}
      getItemName={(setting) => setting.name}
      deleteDescription={(setting) =>
        `This action cannot be undone. This will permanently delete the app setting "${setting.name}".`
      }
      emptyMessage="No app settings found"
      notFoundMessage="No app settings found matching your search"
      // Preserve the original behavior of rendering all rows without pagination
      // (DataTable treats a falsy pageSize as "no pagination").
      pageSize={0}
      groupBy={(setting) => setting.type || "Unknown"}
      renderGroupHeader={(type, items) => (items.length >= 2 ? type : null)}
      columns={columns}
      rowActions={{
        onEdit: (setting) => onEditSetting?.(setting),
        editTitle: "Edit App Setting",
        deleteTitle: "Delete App Setting",
      }}
    />
  );
}
