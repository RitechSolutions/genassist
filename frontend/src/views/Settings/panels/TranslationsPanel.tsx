import { useState } from "react";
import { Translation } from "@/interfaces/translation.interface";
import { TranslationsCard } from "../components/TranslationsCard";
import { TranslationDialog } from "../components/TranslationDialog";
import { PanelHeader, type PanelVariant } from "./PanelHeader";

/**
 * Self-contained Translations experience (header + table + dialog). Rendered
 * both by the standalone `/settings/translations` route (variant="page") and
 * by the Translations tab on the Settings page (variant="tab").
 */
export function TranslationsPanel({ variant = "page" }: { variant?: PanelVariant }) {
  const [searchQuery, setSearchQuery] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [translationToEdit, setTranslationToEdit] = useState<Translation | null>(null);

  const handleRefresh = () => {
    setRefreshKey((prev) => prev + 1);
  };

  const handleOpenCreate = () => {
    setDialogMode("create");
    setTranslationToEdit(null);
    setIsDialogOpen(true);
  };

  const handleOpenEdit = (translation: Translation | null, mode: "create" | "edit") => {
    setDialogMode(mode);
    setTranslationToEdit(translation);
    setIsDialogOpen(true);
  };

  return (
    <div className="space-y-6">
      <PanelHeader
        variant={variant}
        title="Translations"
        subtitle="View and manage application translations"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search translations..."
        secondaryActionText="Refresh"
        onSecondaryAction={handleRefresh}
        actionButtonText="Add Translation"
        onActionClick={handleOpenCreate}
      />

      <TranslationsCard
        searchQuery={searchQuery}
        refreshKey={refreshKey}
        onEditTranslation={handleOpenEdit}
        onAddTranslation={handleOpenCreate}
      />

      <TranslationDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        mode={dialogMode}
        translationToEdit={translationToEdit}
        onTranslationSaved={handleRefresh}
      />
    </div>
  );
}
