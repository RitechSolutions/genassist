import { useState } from "react";
import { Search, Plus } from "lucide-react";
import { FeatureFlag } from "@/interfaces/featureFlag.interface";
import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { useIsMobile } from "@/hooks/useMobile";
import { Button } from "@/components/button";
import { FeatureFlagsCard } from "../components/FeatureFlagsCard";
import { FeatureFlagDialog } from "../components/FeatureFlagDialog";

export function FeatureFlags() {
  const isMobile = useIsMobile();
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [featureFlagToEdit, setFeatureFlagToEdit] = useState<FeatureFlag | null>(null);

  const handleFeatureFlagSaved = () => {
    setRefreshKey(prevKey => prevKey + 1);
  };

  const handleCreateFeatureFlag = () => {
    setDialogMode('create');
    setFeatureFlagToEdit(null);
    setIsDialogOpen(true);
  };
  
  const handleEditFeatureFlag = (featureFlag: FeatureFlag) => {
    setDialogMode('edit');
    setFeatureFlagToEdit(featureFlag);
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
                  <h1 className="text-3xl font-bold mb-2 animate-fade-down">Feature Flags</h1>
                  <p className="text-muted-foreground animate-fade-up">View and manage application feature flags</p>
                </div>
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <input
                      type="text"
                      placeholder="Search feature flags..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <Button 
                    className="flex items-center gap-2"
                    onClick={handleCreateFeatureFlag}
                  >
                    <Plus className="w-4 h-4" />
                    Add New Flag
                  </Button>
                </div>
              </div>
              <FeatureFlagsCard 
                searchQuery={searchQuery} 
                refreshKey={refreshKey}
                onEditFeatureFlag={handleEditFeatureFlag}
              />
            </div>
          </div>
        </main>
      </div>
      <FeatureFlagDialog 
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onFeatureFlagSaved={handleFeatureFlagSaved}
        featureFlagToEdit={featureFlagToEdit}
        mode={dialogMode}
      />
    </SidebarProvider>
  );
} 