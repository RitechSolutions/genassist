import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { LocalFineTuneJobsCard } from "@/views/LocalFineTune/components/LocalFineTuneJobsCard";
import { LocalFineTuneJobDialog } from "@/views/LocalFineTune/components/LocalFineTuneJobDialog";

export default function LocalFineTune() {
  const [searchQuery, setSearchQuery] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const handleJobCreated = () => {
    setRefreshKey((k) => k + 1);
  };

  return (
    <PageLayout>
      <PageHeader
        title="Local Fine-Tune"
        subtitle="Create and manage local fine-tuning jobs (separate server)"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search jobs..."
        actionButtonText="New Local Fine-Tune Job"
        onActionClick={() => setIsDialogOpen(true)}
      />

      <LocalFineTuneJobsCard searchQuery={searchQuery} refreshKey={refreshKey} />

      <LocalFineTuneJobDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onJobCreated={handleJobCreated}
      />
    </PageLayout>
  );
}
