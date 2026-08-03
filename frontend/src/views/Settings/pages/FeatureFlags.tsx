import { PageLayout } from "@/components/PageLayout";
import { FeatureFlagsPanel } from "../panels/FeatureFlagsPanel";

export function FeatureFlags() {
  return (
    <PageLayout>
      <FeatureFlagsPanel variant="page" />
    </PageLayout>
  );
}
