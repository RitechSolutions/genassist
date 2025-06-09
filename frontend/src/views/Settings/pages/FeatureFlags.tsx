import { useState } from "react";
import { FeatureFlag } from "@/interfaces/featureFlag.interface";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { FeatureFlagsCard } from "../components/FeatureFlagsCard";
import { FeatureFlagDialog } from "../components/FeatureFlagDialog";

export function FeatureFlags() {
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
    <PageLayout>
      <PageHeader
        title="Feature Flags"
        subtitle="View and manage application feature flags"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search feature flags..."
        actionButtonText="Add New Flag"
        onActionClick={handleCreateFeatureFlag}
      />
      
      <FeatureFlagsCard 
        searchQuery={searchQuery} 
        refreshKey={refreshKey}
        onEditFeatureFlag={handleEditFeatureFlag}
      />

      <FeatureFlagDialog 
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onFeatureFlagSaved={handleFeatureFlagSaved}
        featureFlagToEdit={featureFlagToEdit}
        mode={dialogMode}
      />
    </PageLayout>
  );
} 