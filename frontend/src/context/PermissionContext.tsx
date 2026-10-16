import React, {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useState,
  useEffect,
  useRef,
} from "react";
import { apiRequest } from "@/config/api";
import { isServerDown } from "@/config/serverStatus";
import { PermissionFetchResult, PermissionRequestGate } from "@/helpers/permissionRetry";
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

  const fetchPermissions = async (): Promise<PermissionFetchResult> => {
    if (!isAuthenticated()) {
      setIsLoading(false);
      return "skipped";
    }

    // If server is down avoid requests
    if (isServerDown() || (typeof navigator !== 'undefined' && !navigator.onLine)) {
      setIsLoading(false);
      return "skipped";
    }

    setIsLoading(true);
    try {
      const response = await apiRequest<AuthMeResponse>("GET", "/auth/me");
      // No answer (e.g. a refused request) keeps the current list, matching what stays in storage
      if (!response) return "failed";
      persistAuthMe(response);
      applySentryUserFromMeResponse(response);
      setPermissions(response.permissions || []);
      return "answered";
    } catch (error) {
      // A down server is retried once it is back, without using up a retry
      return (error as Error)?.message === "SERVER_DOWN" ? "skipped" : "failed";
    } finally {
      setIsLoading(false);
    }
  };

  // Created once, so page guards that unmount and remount cannot restart the retries
  const requestGateRef = useRef<PermissionRequestGate | null>(null);
  if (!requestGateRef.current) {
    requestGateRef.current = new PermissionRequestGate(fetchPermissions);
  }

  useEffect(() => {
    const requestGate = requestGateRef.current;
    void requestGate?.fetchNow();
    return () => requestGate?.dispose();
  }, []);

  const refreshPermissions = useCallback(async () => {
    requestGateRef.current?.request();
  }, []);

  return (
    <PermissionContext.Provider
      value={{
        permissions,
        isLoading,
        refreshPermissions,
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
