import { useState } from "react";
import { FeatureFlag } from "@/interfaces/featureFlag.interface";
import { FeatureFlagsCard } from "../components/FeatureFlagsCard";
import { FeatureFlagDialog } from "../components/FeatureFlagDialog";
import { PanelHeader, type PanelVariant } from "./PanelHeader";

/**
 * Self-contained Feature Flags experience (header + table + dialog). Rendered
 * both by the standalone `/settings/feature-flags` route (variant="page") and
 * by the Feature Flags tab on the Settings page (variant="tab").
 */
export function FeatureFlagsPanel({ variant = "page" }: { variant?: PanelVariant }) {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [featureFlagToEdit, setFeatureFlagToEdit] = useState<FeatureFlag | null>(null);

  const handleFeatureFlagSaved = () => {
    setRefreshKey((prevKey) => prevKey + 1);
  };

  const handleCreateFeatureFlag = () => {
    setDialogMode("create");
    setFeatureFlagToEdit(null);
    setIsDialogOpen(true);
  };

  const handleEditFeatureFlag = (featureFlag: FeatureFlag) => {
    setDialogMode("edit");
    setFeatureFlagToEdit(featureFlag);
    setIsDialogOpen(true);
  };

  return (
    <div className="space-y-6">
      <PanelHeader
        variant={variant}
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
        onCreateFeatureFlag={handleCreateFeatureFlag}
      />

      <FeatureFlagDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onFeatureFlagSaved={handleFeatureFlagSaved}
        featureFlagToEdit={featureFlagToEdit}
        mode={dialogMode}
      />
    </div>
  );
}
