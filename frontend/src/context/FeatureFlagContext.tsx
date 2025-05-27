import React, { createContext, useContext, useState, useEffect, ReactNode, useMemo } from 'react';
import { getFeatureFlags } from '@/services/featureFlags';
import { FeatureFlag, ParsedFeatureFlag } from '@/interfaces/featureFlag.interface';
import { parseFeatureFlags, isFeatureEnabled as checkFeatureEnabled, getFeatureValue as getFeatureValueHelper } from '@/helpers/featureFlag';

interface FeatureFlagContextType {
  flags: FeatureFlag[];
  loading: boolean;
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
  const [error, setError] = useState<string | null>(null);

  const fetchFlags = async () => {
    try {
      setLoading(true);
      const fetchedFlags = await getFeatureFlags();
      setFlags(fetchedFlags);
      setError(null);
    } catch (err) {
      console.error('Error fetching feature flags:', err);
      setError('Failed to load feature flags');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFlags();
  }, []);

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