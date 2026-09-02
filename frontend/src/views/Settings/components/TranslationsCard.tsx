import { Column } from "@/components/ui/data-table";
import { EntityTableCard } from "@/components/EntityTableCard";
import { Button } from "@/components/button";
import { Languages, Plus } from "lucide-react";
import { deleteTranslation, getTranslations } from "@/services/translations";
import { Translation } from "@/interfaces/translation.interface";

interface TranslationsCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditTranslation: (
    translation: Translation | null,
    mode: "create" | "edit"
  ) => void;
  onAddTranslation: () => void;
}

export function TranslationsCard({
  searchQuery,
  refreshKey = 0,
  onEditTranslation,
  onAddTranslation,
}: TranslationsCardProps) {
  const cellClass =
    "max-w-[200px] truncate whitespace-nowrap overflow-hidden text-ellipsis align-middle";
  const longCellClass =
    "max-w-[280px] truncate whitespace-nowrap overflow-hidden text-ellipsis align-middle";

  const columns: Column<Translation>[] = [
    {
      header: "Key",
      key: "key",
      headerClassName: "w-48",
      className: cellClass,
      cell: (row) => <span title={row.key}>{row.key}</span>,
    },
    {
      header: "Default",
      key: "default",
      headerClassName: "w-64",
      className: longCellClass,
      cell: (row) => <span title={row.default ?? ""}>{row.default ?? ""}</span>,
    },
    {
      header: "Languages",
      key: "languages",
      headerClassName: "w-48",
      className: cellClass,
      cell: (row) => {
        const langCodes = Object.keys(row.translations)
          .filter((code) => row.translations[code]?.trim())
          .map((code) => code.toUpperCase());
        return langCodes.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {langCodes.map((code) => (
              <span
                key={code}
                className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs font-medium"
              >
                {code}
              </span>
            ))}
          </div>
        ) : (
          <span className="text-muted-foreground text-sm">None</span>
        );
      },
    },
  ];

  return (
    <EntityTableCard<Translation>
      entityName="translation"
      searchQuery={searchQuery}
      filterFn={(t, query) => {
        const q = query.trim().toLowerCase();
        const values = [t.key, t.default, ...Object.values(t.translations)]
          .filter(Boolean)
          .map((v) => String(v).toLowerCase());
        return values.some((v) => v.includes(q));
      }}
      refreshKey={refreshKey}
      fetchFn={getTranslations}
      getItemId={(t) => t.key}
      deleteFn={(t) => deleteTranslation(t.key)}
      getItemName={(t) => t.key}
      deleteDescription={(t) =>
        `This action cannot be undone. This will permanently delete the translation "${t.key}".`
      }
      fetchErrorMessage="Failed to fetch translations."
      deleteSuccessMessage="Translation deleted."
      deleteErrorMessage="Failed to delete translation."
      emptyMessage="No translations found"
      notFoundMessage="No translations found matching your search"
      emptyState={{
        icon: <Languages className="h-12 w-12 text-muted-foreground" />,
        title: "No translations yet",
        searchTitle: "No matching translations",
        description:
          "Add translation keys and locale strings so the app can display copy for each language.",
        searchDescription: "Try adjusting your search query.",
        action: (
          <Button
            onClick={onAddTranslation}
            className="rounded-full flex items-center gap-2"
          >
            <Plus className="h-4 w-4" />
            Add Translation
          </Button>
        ),
      }}
      columns={columns}
      rowActions={{
        onEdit: (t) => onEditTranslation(t, "edit"),
        editTitle: "Edit translation",
        deleteTitle: "Delete translation",
        canDelete: (t) => !!t.key,
        headerClassName: "w-28",
      }}
    />
  );
}
