import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { AppSettingsCard } from "@/views/AppSettings/components/AppSettingsCard";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { AppSettingDialog } from "../components/AppSettingDialog";

export default function AppSettings() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [settingToEdit, setSettingToEdit] = useState<AppSetting | null>(null);

  const handleSettingSaved = () => {
    setRefreshKey(prevKey => prevKey + 1);
  };

  const handleCreateSetting = () => {
    setDialogMode('create');
    setSettingToEdit(null);
    setIsDialogOpen(true);
  };
  
  const handleEditSetting = (setting: AppSetting) => {
    setDialogMode('edit');
    setSettingToEdit(setting);
    setIsDialogOpen(true);
  };

  return (
    <PageLayout>
      <PageHeader
        title="App Settings"
        subtitle="View and manage application configuration settings"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search settings..."
        actionButtonText="Add New Setting"
        onActionClick={handleCreateSetting}
      />
      
      <AppSettingsCard 
        searchQuery={searchQuery}
        refreshKey={refreshKey}
        onEditSetting={handleEditSetting}
      />

      <AppSettingDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onSettingCreated={handleSettingSaved}
        settingToEdit={settingToEdit}
        mode={dialogMode}
      />
    </PageLayout>
  );
} 