import { SectionTitle } from "@/components/Heading";
import { BackfillStatsCard } from "../components/maintenance/BackfillStatsCard";
import type { PanelVariant } from "./PanelHeader";

/**
 * Admin maintenance / background-jobs experience. Hosts one card per
 * operational job. Rendered both by the standalone `/settings/maintenance`
 * route (variant="page") and by the Maintenance tab on the Settings page
 * (variant="tab"). Gated behind the "write:app_settings" permission by both
 * entry points.
 */
export function MaintenancePanel({ variant = "page" }: { variant?: PanelVariant }) {
  return (
    <div className="space-y-6">
      {variant === "page" ? (
        <header>
          <h1 className="text-2xl sm:text-3xl font-bold mb-2 animate-fade-down">Maintenance</h1>
          <p className="text-sm sm:text-base text-muted-foreground animate-fade-up">
            Run one-off background jobs and data maintenance tasks.
          </p>
        </header>
      ) : (
        <div className="min-w-0">
          <SectionTitle className="text-lg sm:text-xl animate-fade-down">Maintenance</SectionTitle>
          <p className="text-sm text-muted-foreground animate-fade-up">
            Run one-off background jobs and data maintenance tasks.
          </p>
        </div>
      )}

      <div className="space-y-4">
        <BackfillStatsCard />
      </div>
    </div>
  );
}
