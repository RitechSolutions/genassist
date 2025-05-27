import React, {
  ReactNode,
  createContext,
  useContext,
  useState,
  useEffect,
} from "react";
import { apiRequest } from "@/config/api";
import { isAuthenticated } from "@/services/auth";

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
  const [permissions, setPermissions] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchPermissions = async () => {
    if (!isAuthenticated()) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const response = await apiRequest("GET", "/auth/me");
      const userPermissions: string[] =
        (response as { permissions: string[] })?.permissions || [];
      setPermissions(userPermissions);
    } catch (error) {
      console.error("Error fetching user permissions:", error);
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
