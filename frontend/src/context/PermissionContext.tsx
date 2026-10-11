import React, {
  ReactNode,
  createContext,
  useContext,
  useState,
  useEffect,
} from "react";
import { apiRequest } from "@/config/api";
import { isServerDown } from "@/config/serverStatus";
import { applySentryUserFromMeResponse } from "@/plugins/sentryUserSync";
import { AuthMeResponse, getPermissions, isAuthenticated, persistAuthMe } from "@/services/auth";

interface PermissionContextType {
  permissions: string[];
  isLoading: boolean;
  refreshPermissions: () => Promise<void>;
}

interface PermissionProviderProps {
  children: ReactNode;
}

const PermissionContext = createContext<PermissionContextType | undefined>(
  undefined
);

export const PermissionProvider: React.FC<PermissionProviderProps> = ({
  children,
}) => {
  // Start from the stored list so screens and services agree until /auth/me answers
  const [permissions, setPermissions] = useState<string[]>(() =>
    isAuthenticated() ? getPermissions() : []
  );
  const [isLoading, setIsLoading] = useState(true);

  const fetchPermissions = async () => {
    if (!isAuthenticated()) {
      setIsLoading(false);
      return;
    }

    // If server is down avoid requests
    if (isServerDown() || (typeof navigator !== 'undefined' && !navigator.onLine)) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const response = await apiRequest<AuthMeResponse>("GET", "/auth/me");
      // No answer (e.g. a refused request) keeps the current list, matching what stays in storage
      if (response) {
        persistAuthMe(response);
        applySentryUserFromMeResponse(response);
        setPermissions(response.permissions || []);
      }
    } catch (error) {
      // Quiet known down-state errors
      if ((error as Error)?.message !== 'SERVER_DOWN') {
        // ignore
      }
    }
    setIsLoading(false);
  };

  useEffect(() => {
    fetchPermissions();
  }, []);

  return (
    <PermissionContext.Provider
      value={{
        permissions,
        isLoading,
        refreshPermissions: fetchPermissions,
      }}
    >
      {children}
    </PermissionContext.Provider>
  );
};

export const usePermissions = (): string[] => {
  const context = useContext(PermissionContext);
  if (!context) {
    throw new Error("usePermissions must be used within a PermissionProvider");
  }
  return context.permissions;
};

export const useIsLoadingPermissions = (): boolean => {
  const context = useContext(PermissionContext);
  if (!context) {
    throw new Error(
      "useIsLoadingPermissions must be used within a PermissionProvider"
    );
  }
  return context.isLoading;
};

export const useRefreshPermissions = (): (() => Promise<void>) => {
  const context = useContext(PermissionContext);
  if (!context) {
    throw new Error(
      "useRefreshPermissions must be used within a PermissionProvider"
    );
  }
  return context.refreshPermissions;
};
