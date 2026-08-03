import { Navigate, useLocation } from "react-router-dom";
import { isAuthenticated, isPasswordUpdateRequired } from "@/services/auth";
import {
  usePermissions,
  useIsLoadingPermissions,
  useRefreshPermissions,
} from "@/context/PermissionContext";
import RouteLoadingFallback from "@/layout/RouteLoadingFallback";
import { useEffect } from "react";
import { useServerStatus } from "@/context/ServerStatusContext";

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredPermissions?: string | string[];
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredPermissions = [],
}) => {
  const location = useLocation();
  const permissions = usePermissions();
  const isLoading = useIsLoadingPermissions();
  const refreshPermissions = useRefreshPermissions();
  const { status, isOffline } = useServerStatus();
  // Removed proactive refresh to avoid duplicate API calls when server is down

  useEffect(() => {
    if (
      isAuthenticated() &&
      permissions.length === 0 &&
      !isLoading &&
      !(status.down || isOffline)
    ) {
      refreshPermissions();
    }
  }, [permissions, isLoading, refreshPermissions, status.down, isOffline]);

  if (!isAuthenticated()) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Allow access to change-password route even if password update is required
  if (isPasswordUpdateRequired() && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" state={{ from: location }} replace />;
  }

  if (isLoading) {
    return <RouteLoadingFallback />;
  }

  if (
    permissions.length === 0 &&
    Array.isArray(requiredPermissions) &&
    requiredPermissions.length > 0
  ) {
    return <RouteLoadingFallback />;
  }

  const normalize = (input?: string | string[]) =>
    typeof input === "string" ? [input] : input ?? [];

  const required = normalize(requiredPermissions);
  const hasFullAccess = permissions.includes("*");
  const hasPermission = required.some((p) => permissions.includes(p));

  if (
    required.length > 0 &&
    !hasFullAccess &&
    !hasPermission
  ) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
