import { PageLayout } from "@/components/PageLayout";
import { MaintenancePanel } from "../panels/MaintenancePanel";

/**
 * Admin maintenance / background-jobs page. Gated behind the
 * "write:app_settings" permission at the route level (see Routes.tsx).
 */
export function Maintenance() {
  return (
    <PageLayout>
      <MaintenancePanel variant="page" />
    </PageLayout>
  );
}
