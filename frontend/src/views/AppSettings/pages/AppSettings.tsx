import { useEffect, useState } from "react";
import { getAllAppSettings, deleteAppSetting } from "@/services/appSettings";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { AppSettingsCard } from "@/views/AppSettings/components/AppSettingsCard";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { AppSettingDialog } from "../components/AppSettingDialog";
import { toast } from "react-hot-toast";

export default function AppSettings() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [settingToEdit, setSettingToEdit] = useState<AppSetting | null>(
    null
  );

  const [appSettings, setAppSettings] = useState<AppSetting[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const data = await getAllAppSettings();
        setAppSettings(data);
      } catch (error) {
        setError(
          "We couldn't load your configuration variables. Please try again."
        );
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [refreshKey]);

  const handleRetry = () => setRefreshKey((prevKey) => prevKey + 1);

  const handleSettingSaved = (_?: AppSetting) => {
    setRefreshKey((prevKey) => prevKey + 1);
  };

  const handleCreateSetting = () => {
    setDialogMode("create");
    setSettingToEdit(null);
    setIsDialogOpen(true);
  };

  const handleEditSetting = (setting: AppSetting) => {
    setDialogMode("edit");
    setSettingToEdit(setting);
    setIsDialogOpen(true);
  };

  const handleDeleteSetting = async (id: string) => {
    try {
      await deleteAppSetting(id);
      setRefreshKey((prev) => prev + 1);
    } catch (error) {
      toast.error("Failed to delete app setting.");
    }
  };

  return (
    <PageLayout>
      <PageHeader
        title="Configuration Vars"
        subtitle="View and manage application configuration variables"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search configuration..."
        actionButtonText="Add New Configuration"
        onActionClick={handleCreateSetting}
      />

      <AppSettingsCard
        searchQuery={searchQuery}
        refreshKey={refreshKey}
        appSettings={appSettings}
        loading={isLoading}
        error={error}
        onRetry={handleRetry}
        onCreateSetting={handleCreateSetting}
        onEditSetting={handleEditSetting}
        onDeleteSetting={handleDeleteSetting}
      />

      <AppSettingDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onSettingSaved={handleSettingSaved}
        settingToEdit={settingToEdit}
        mode={dialogMode}
      />
    </PageLayout>
  );
} 