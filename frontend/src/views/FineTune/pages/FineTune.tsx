import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { FineTuneJobsCard } from "@/views/FineTune/components/FineTuneJobsCard";
import { FineTuneJobDialog } from "@/views/FineTune/components/FineTuneJobDialog";

export default function FineTune() {
  const [searchQuery, setSearchQuery] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const handleJobCreated = () => {
    setRefreshKey((k) => k + 1);
  };

  return (
    <PageLayout>
      <PageHeader
        title="Fine-Tune"
        subtitle="Create and manage fine-tuning jobs"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search jobs..."
        actionButtonText="New Fine-Tune Job"
        onActionClick={() => setIsDialogOpen(true)}
      />

      <FineTuneJobsCard searchQuery={searchQuery} refreshKey={refreshKey} />

      <FineTuneJobDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onJobCreated={handleJobCreated}
      />
    </PageLayout>
  );
}