import { Navigate, useLocation } from "react-router-dom";
import { isAuthenticated } from "@/services/auth";
import {
  usePermissions,
  useIsLoadingPermissions,
  useRefreshPermissions,
} from "@/context/PermissionContext";
import { Skeleton } from "@/components/skeleton";
import { useEffect } from "react";

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

  useEffect(() => {
    if (isAuthenticated() && permissions.length === 0 && !isLoading) {
      refreshPermissions();
    }
  }, [permissions, isLoading, refreshPermissions]);

  if (!isAuthenticated()) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="flex flex-col space-y-3">
          <Skeleton className="h-[125px] w-[250px] rounded-xl" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-[250px]" />
            <Skeleton className="h-4 w-[200px]" />
          </div>
        </div>
      </div>
    );
  }

  if (
    permissions.length === 0 &&
    Array.isArray(requiredPermissions) &&
    requiredPermissions.length > 0
  ) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="flex flex-col space-y-3">
          <Skeleton className="h-[125px] w-[250px] rounded-xl" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-[250px]" />
            <Skeleton className="h-4 w-[200px]" />
          </div>
        </div>
      </div>
    );
  }

  const normalize = (input?: string | string[]) =>
    typeof input === "string" ? [input] : input ?? [];

  const required = normalize(requiredPermissions);
  const hasFullAccess = permissions.includes("*");

  if (
    required.length > 0 &&
    !hasFullAccess &&
    !required.every((p) => permissions.includes(p))
  ) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
