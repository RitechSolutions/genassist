import { useState } from "react";
import { Info } from "lucide-react";
import { Card, CardContent } from "@/components/card";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { useLocalFineTuneJobs } from "@/hooks/useLocalFineTuneJobs";
import { LocalFineTuneListSummary } from "@/views/LocalFineTune/components/LocalFineTuneListSummary";
import { LocalFineTuneJobsCard } from "@/views/LocalFineTune/components/LocalFineTuneJobsCard";
import { LocalFineTuneJobDialog } from "@/views/LocalFineTune/components/LocalFineTuneJobDialog";

export default function LocalFineTune() {
  const [searchQuery, setSearchQuery] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const { jobs, setJobs, loading, error } = useLocalFineTuneJobs(refreshKey);

  const handleJobCreated = () => {
    setRefreshKey((k) => k + 1);
  };

  return (
    <PageLayout>
      <PageHeader
        title="Local Fine-Tune"
        subtitle="Run and monitor LoRA jobs on your local trainer (separate API)"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search jobs..."
        actionButtonText="New Local Fine-Tune Job"
        onActionClick={() => setIsDialogOpen(true)}
      />

      <LocalFineTuneListSummary jobs={jobs} loading={loading} />

      {!loading && jobs.length === 0 && !error && (
        <Card className="bg-blue-50/90 border-blue-200/80 shadow-sm animate-fade-up">
          <CardContent className="p-4 flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
            <p className="text-sm text-blue-900 leading-relaxed">
              No jobs yet. Start a run from this page to see status, training loss, and event logs
              on the detail view—same layout patterns as cloud Fine-Tune and Agent Performance.
            </p>
          </CardContent>
        </Card>
      )}

      <LocalFineTuneJobsCard
        jobs={jobs}
        setJobs={setJobs}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
      />

      <LocalFineTuneJobDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onJobCreated={handleJobCreated}
      />
    </PageLayout>
  );
}
