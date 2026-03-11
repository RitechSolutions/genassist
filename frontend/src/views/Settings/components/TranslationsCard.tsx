import { useEffect, useMemo, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { TableCell, TableRow } from "@/components/table";
import { Button } from "@/components/button";
import { Pencil, Trash2 } from "lucide-react";
import { toast } from "react-hot-toast";
import { deleteTranslation, getTranslations } from "@/services/translations";
import { Translation } from "@/interfaces/translation.interface";
import { ConfirmDialog } from "@/components/ConfirmDialog";

const HEADERS = [
  { label: "Key", className: "w-48" },
  { label: "Default", className: "w-64" },
  { label: "Languages", className: "w-48" },
  { label: "Actions", className: "w-28" },
];

interface TranslationsCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditTranslation: (
    translation: Translation | null,
    mode: "create" | "edit"
  ) => void;
  onRefresh: () => void;
}

export function TranslationsCard({
  searchQuery,
  refreshKey = 0,
  onEditTranslation,
  onRefresh,
}: TranslationsCardProps) {
  const [translations, setTranslations] = useState<Translation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [translationToDelete, setTranslationToDelete] =
    useState<Translation | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const fetchTranslations = async () => {
      try {
        setLoading(true);
        const data = await getTranslations();
        setTranslations(data);
        setError(null);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to fetch translations"
        );
        toast.error("Failed to fetch translations.");
      } finally {
        setLoading(false);
      }
    };

    fetchTranslations();
  }, [refreshKey]);

  const handleDeleteClick = (row: Translation) => {
    if (!row.key) return;
    setTranslationToDelete(row);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!translationToDelete?.key) return;

    try {
      setIsDeleting(true);
      await deleteTranslation(translationToDelete.key);
      toast.success("Translation deleted.");

      setTranslations((prev) =>
        prev.filter((t) => t.key !== translationToDelete.key)
      );
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to delete translation."
      );
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setTranslationToDelete(null);
    }
  };

  const filteredTranslations = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return translations;

    return translations.filter((t) => {
      const values = [
        t.key,
        t.default,
        ...Object.values(t.translations),
      ]
        .filter(Boolean)
        .map((v) => String(v).toLowerCase());

      return values.some((v) => v.includes(q));
    });
  }, [translations, searchQuery]);

  const renderRow = (row: Translation) => {
    const cellClass =
      "max-w-[200px] truncate whitespace-nowrap overflow-hidden text-ellipsis align-middle";
    const longCellClass =
      "max-w-[280px] truncate whitespace-nowrap overflow-hidden text-ellipsis align-middle";

    const langCodes = Object.keys(row.translations)
      .filter((code) => row.translations[code]?.trim())
      .map((code) => code.toUpperCase());

    return (
      <TableRow key={row.id || row.key}>
        <TableCell className={cellClass} title={row.key}>
          {row.key}
        </TableCell>
        <TableCell className={longCellClass} title={row.default ?? ""}>
          {row.default ?? ""}
        </TableCell>
        <TableCell className={cellClass}>
          {langCodes.length > 0 ? (
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
          )}
        </TableCell>
        <TableCell>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onEditTranslation(row, "edit")}
              title="Edit translation"
            >
              <Pencil className="w-4 h-4 text-black" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => handleDeleteClick(row)}
              title="Delete translation"
            >
              <Trash2 className="w-4 h-4 text-red-500" />
            </Button>
          </div>
        </TableCell>
      </TableRow>
    );
  };

  return (
    <>
      <div className="flex justify-between items-center mb-3">
        <h2 className="text-lg font-semibold">Translations</h2>
        <Button
          variant="outline"
          size="sm"
          className="flex items-center gap-1"
          onClick={onRefresh}
        >
          Refresh
        </Button>
      </div>

      <DataTable
        data={filteredTranslations}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        headers={HEADERS}
        renderRow={renderRow}
        emptyMessage="No translations found"
        searchEmptyMessage="No translations found matching your search"
      />

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isInProgress={isDeleting}
        itemName={translationToDelete?.key || ""}
        description={`This action cannot be undone. This will permanently delete the translation "${translationToDelete?.key}".`}
      />
    </>
  );
}
