import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/card";
import { DataTable } from "@/components/DataTable";
import { TableCell, TableRow } from "@/components/table";
import { Button } from "@/components/button";
import { Pencil, Trash2 } from "lucide-react";
import { toast } from "react-hot-toast";
import { deleteTranslation, getTranslations } from "@/services/translations";
import { Translation } from "@/interfaces/translation.interface";
import { ConfirmDialog } from "@/components/ConfirmDialog";

interface TranslationsCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditTranslation: (translation: Translation | null, mode: "create" | "edit") => void;
}

export function TranslationsCard({
  searchQuery,
  refreshKey = 0,
  onEditTranslation,
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

      const fresh = await getTranslations();
      setTranslations(fresh);
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
        t.en,
        t.es,
        t.fr,
        t.de,
        t.pt,
        t.zh,
      ]
        .filter(Boolean)
        .map((v) => String(v).toLowerCase());

      return values.some((v) => v.includes(q));
    });
  }, [translations, searchQuery]);

  const headers = [
    { label: "Key", className: "w-40" },
    { label: "Default", className: "w-40" },
    { label: "EN", className: "w-32" },
    { label: "ES", className: "w-32" },
    { label: "FR", className: "w-32" },
    { label: "DE", className: "w-32" },
    { label: "PT", className: "w-32" },
    { label: "ZH", className: "w-32" },
    { label: "Actions", className: "w-28" },
  ];

  const renderRow = (row: Translation) => {
    const cellClass =
      "max-w-[140px] truncate whitespace-nowrap overflow-hidden text-ellipsis align-middle";
    const longCellClass =
      "max-w-[200px] truncate whitespace-nowrap overflow-hidden text-ellipsis align-middle";

    return (
      <TableRow key={row.id || row.key || Math.random().toString()}>
        <TableCell className={cellClass} title={row.key}>
          {row.key}
        </TableCell>
        <TableCell className={longCellClass} title={row.default ?? ""}>
          {row.default ?? ""}
        </TableCell>
        <TableCell className={cellClass} title={row.en ?? ""}>
          {row.en ?? ""}
        </TableCell>
        <TableCell className={cellClass} title={row.es ?? ""}>
          {row.es ?? ""}
        </TableCell>
        <TableCell className={cellClass} title={row.fr ?? ""}>
          {row.fr ?? ""}
        </TableCell>
        <TableCell className={cellClass} title={row.de ?? ""}>
          {row.de ?? ""}
        </TableCell>
        <TableCell className={cellClass} title={row.pt ?? ""}>
          {row.pt ?? ""}
        </TableCell>
        <TableCell className={cellClass} title={row.zh ?? ""}>
          {row.zh ?? ""}
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
          onClick={() => onEditTranslation(null, "create")}
        >
          Add Translation
        </Button>
      </div>

      <DataTable
        data={filteredTranslations}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        headers={headers}
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

