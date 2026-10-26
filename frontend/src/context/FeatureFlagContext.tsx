import React, { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';
import { FEATURE_FLAG_READ_PERMISSION, getFeatureFlagsForCurrentUser } from '@/services/featureFlags';
import { useHasPermission } from '@/hooks/useHasPermission';
import { useIsLoadingPermissions } from '@/context/PermissionContext';
import { FeatureFlag, ParsedFeatureFlag } from '@/interfaces/featureFlag.interface';
import { parseFeatureFlags, isFeatureEnabled as checkFeatureEnabled, getFeatureValue as getFeatureValueHelper } from '@/helpers/featureFlag';
import { isAuthenticated } from '@/services/auth';

interface FeatureFlagContextType {
  flags: FeatureFlag[];
  loading: boolean;
  /** Latches true once the first fetch settles; never returns to false. */
  hydrated: boolean;
  error: string | null;
  isEnabled: (key: string) => boolean;
  getValue: (key: string) => string | null;
  getFeatureItems: (prefix: string) => ParsedFeatureFlag[];
  getFeatureItem: (key: string) => ParsedFeatureFlag | undefined;
  refreshFlags: () => Promise<void>;
}

const FeatureFlagContext = createContext<FeatureFlagContextType | undefined>(undefined);

interface FeatureFlagProviderProps {
  children: ReactNode;
}

export const FeatureFlagProvider: React.FC<FeatureFlagProviderProps> = ({ children }) => {
  const [flags, setFlags] = useState<FeatureFlag[]>([]);
  const [loading, setLoading] = useState(true);
  const [hydrated, setHydrated] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canReadFlags = useHasPermission(FEATURE_FLAG_READ_PERMISSION);
  const isLoadingPermissions = useIsLoadingPermissions();
  // A stored list without the permission may be out of date, so /auth/me decides
  const isAwaitingPermissions = !canReadFlags && isLoadingPermissions;
  const latestRequestRef = useRef(0);

  const fetchFlags = async () => {
    const requestId = ++latestRequestRef.current;
    const isLatestRequest = () => requestId === latestRequestRef.current;
    try {
      setLoading(true);
      const fetchedFlags = await getFeatureFlagsForCurrentUser();
      if (!isLatestRequest()) return;
      setFlags(fetchedFlags);
      setError(null);
    } catch (err) {
      if (!isLatestRequest()) return;
      setError('Failed to load feature flags');
    } finally {
      if (isLatestRequest()) {
        setLoading(false);
        setHydrated(true);
      }
    }
  };

  // Reload when the user's access to flags changes, e.g. once /auth/me answers
  useEffect(() => {
    if (!isAuthenticated()) {
      // no fetch runs for anonymous visitors, so flag state is already final
      setHydrated(true);
      return;
    }
    if (isAwaitingPermissions) return;
    fetchFlags();
  }, [canReadFlags, isAwaitingPermissions]);

  const isEnabled = (key: string): boolean => {
    return checkFeatureEnabled(flags, key);
  };

  const getValue = (key: string): string | null => {
    return getFeatureValueHelper(flags, key);
  };

  const getFeatureItems = (prefix: string): ParsedFeatureFlag[] => {
    return parseFeatureFlags(flags, prefix);
  };

  const getFeatureItem = (key: string): ParsedFeatureFlag | undefined => {
    return getFeatureItems(key)[0];
  };

  const refreshFlags = async (): Promise<void> => {
    await fetchFlags();
  };

  const value = {
    flags,
    loading,
    hydrated,
    error,
    isEnabled,
    getValue,
    getFeatureItems,
    getFeatureItem,
    refreshFlags
  };

  return (
    <FeatureFlagContext.Provider value={value}>
      {children}
    </FeatureFlagContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useFeatureFlag = (): FeatureFlagContextType => {
  const context = useContext(FeatureFlagContext);
  if (context === undefined) {
    throw new Error('useFeatureFlag must be used within a FeatureFlagProvider');
  }
  return context;
}; 