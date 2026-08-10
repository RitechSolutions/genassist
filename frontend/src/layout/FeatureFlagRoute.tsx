import { Navigate } from "react-router-dom";
import { useFeatureFlagVisible } from "@/components/featureFlag";
import { useFeatureFlag } from "@/context/FeatureFlagContext";
import RouteLoadingFallback from "@/layout/RouteLoadingFallback";

interface FeatureFlagRouteProps {
  children: React.ReactNode;
  flagKey: string;
}

const FeatureFlagRoute: React.FC<FeatureFlagRouteProps> = ({ children, flagKey }) => {
  const { hydrated } = useFeatureFlag();
  const isVisible = useFeatureFlagVisible(flagKey);

  // Hold the route until flags settle, otherwise a refresh reads as a disabled flag
  if (!hydrated) {
    return <RouteLoadingFallback />;
  }

  if (!isVisible) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};

export default FeatureFlagRoute;
