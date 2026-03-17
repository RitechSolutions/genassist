import { useState } from "react";
import { Language } from "@/interfaces/translation.interface";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { LanguagesCard } from "../components/LanguagesCard";
import { LanguageDialog } from "../components/LanguageDialog";

export function Languages() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [languageToEdit, setLanguageToEdit] = useState<Language | null>(null);

  const handleLanguageSaved = () => {
    setRefreshKey((prevKey) => prevKey + 1);
  };

  const handleCreateLanguage = () => {
    setDialogMode("create");
    setLanguageToEdit(null);
    setIsDialogOpen(true);
  };

  const handleEditLanguage = (language: Language) => {
    setDialogMode("edit");
    setLanguageToEdit(language);
    setIsDialogOpen(true);
  };

  return (
    <PageLayout>
      <PageHeader
        title="Languages"
        subtitle="View and manage supported languages for translations"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search languages..."
        actionButtonText="Add New Language"
        onActionClick={handleCreateLanguage}
      />

      <LanguagesCard
        searchQuery={searchQuery}
        refreshKey={refreshKey}
        onEditLanguage={handleEditLanguage}
      />

      <LanguageDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onLanguageSaved={handleLanguageSaved}
        languageToEdit={languageToEdit}
        mode={dialogMode}
      />
    </PageLayout>
  );
}
