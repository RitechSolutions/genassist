import { PageLayout } from "@/components/PageLayout";
import { BackfillStatsCard } from "../components/maintenance/BackfillStatsCard";

/**
 * Admin maintenance / background-jobs page. Hosts one card per operational job;
 * add new job cards here as they are introduced. Gated behind the
 * "write:app_settings" permission at the route level (see Routes.tsx).
 */
export function Maintenance() {
  return (
    <PageLayout>
      <header className="mb-2">
        <h1 className="text-2xl sm:text-3xl font-bold mb-2 animate-fade-down">Maintenance</h1>
        <p className="text-sm sm:text-base text-muted-foreground animate-fade-up">
          Run one-off background jobs and data maintenance tasks.
        </p>
      </header>

      <div className="space-y-4">
        <BackfillStatsCard />
      </div>
    </PageLayout>
  );
}
