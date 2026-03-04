import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { TranslationsCard } from "../components/TranslationsCard";
import { TranslationDialog } from "../components/TranslationDialog";
import { Translation } from "@/interfaces/translation.interface";

export function Translations() {
  const [searchQuery, setSearchQuery] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [translationToEdit, setTranslationToEdit] = useState<Translation | null>(null);

  const handleRefresh = () => {
    setRefreshKey((prev) => prev + 1);
  };

  const handleTranslationSaved = () => {
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
    <PageLayout>
      <PageHeader
        title="Translations"
        subtitle="View and manage application translations"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search translations..."
        actionButtonText="Refresh"
        onActionClick={handleRefresh}
      />

      <TranslationsCard
        searchQuery={searchQuery}
        refreshKey={refreshKey}
        onEditTranslation={handleOpenEdit}
      />

      <TranslationDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        mode={dialogMode}
        translationToEdit={translationToEdit || undefined}
        onTranslationSaved={handleTranslationSaved}
      />
    </PageLayout>
  );
}

