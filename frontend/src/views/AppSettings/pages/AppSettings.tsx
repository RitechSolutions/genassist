import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { AppSettingsCard } from "@/views/AppSettings/components/AppSettingsCard";
import { useIsMobile } from "@/hooks/useMobile";
import { Search, Plus } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/button";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { AppSettingDialog } from "../components/AppSettingDialog";

export default function AppSettings() {
  const isMobile = useIsMobile();
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
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100">
          <div className="flex-1 p-8">
            <div className="max-w-7xl mx-auto space-y-6">
              <div className="flex justify-between items-start">
                <div>
                  <h1 className="text-3xl font-bold mb-2 animate-fade-down">App Settings</h1>
                  <p className="text-muted-foreground animate-fade-up">View and manage application configuration settings</p>
                </div>
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <input
                      type="text"
                      placeholder="Search settings..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <Button 
                    className="flex items-center gap-2"
                    onClick={handleCreateSetting}
                  >
                    <Plus className="w-4 h-4" />
                    Add New Setting
                  </Button>
                </div>
              </div>
              <AppSettingsCard 
                searchQuery={searchQuery}
                refreshKey={refreshKey}
                onEditSetting={handleEditSetting}
              />
            </div>
          </div>
        </main>
      </div>
      <AppSettingDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onSettingCreated={handleSettingSaved}
        settingToEdit={settingToEdit}
        mode={dialogMode}
      />
    </SidebarProvider>
  );
} 