import { useState, useEffect, useCallback } from 'react';
import { 
  getFeatureFlags, 
  createFeatureFlag, 
  updateFeatureFlag, 
  deleteFeatureFlag 
} from '@/services/featureFlags';
import { useToast } from '@/components/use-toast';
import { FeatureFlag, FeatureFlagFormData } from '@/interfaces/featureFlag.interface';

export function useFeatureFlags() {
  const [featureFlags, setFeatureFlags] = useState<FeatureFlag[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  const fetchFeatureFlags = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const flags = await getFeatureFlags();
      setFeatureFlags(flags);
    } catch (err) {
      setError('Failed to fetch feature flags');
      toast({
        title: 'Error',
        description: 'Failed to fetch feature flags',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const addFeatureFlag = useCallback(async (data: FeatureFlagFormData) => {
    setLoading(true);
    setError(null);
    try {
      const newFlag = await createFeatureFlag(data);
      if (newFlag) {
        setFeatureFlags(prev => [...prev, newFlag]);
        toast({
          title: 'Success',
          description: 'Feature flag created successfully',
        });
        return true;
      }
      return false;
    } catch (err) {
      setError('Failed to create feature flag');
      toast({
        title: 'Error',
        description: 'Failed to create feature flag',
        variant: 'destructive',
      });
      return false;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const editFeatureFlag = useCallback(async (id: string, data: FeatureFlagFormData) => {
    setLoading(true);
    setError(null);
    try {
      const updatedFlag = await updateFeatureFlag(id, data);
      if (updatedFlag) {
        setFeatureFlags(prev => 
          prev.map(flag => flag.id === id ? updatedFlag : flag)
        );
        toast({
          title: 'Success',
          description: 'Feature flag updated successfully',
        });
        return true;
      }
      return false;
    } catch (err) {
      setError('Failed to update feature flag');
      toast({
        title: 'Error',
        description: 'Failed to update feature flag',
        variant: 'destructive',
      });
      return false;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const removeFeatureFlag = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      await deleteFeatureFlag(id);
      setFeatureFlags(prev => prev.filter(flag => flag.id !== id));
      toast({
        title: 'Success',
        description: 'Feature flag deleted successfully',
      });
      return true;
    } catch (err) {
      setError('Failed to delete feature flag');
      toast({
        title: 'Error',
        description: 'Failed to delete feature flag',
        variant: 'destructive',
      });
      return false;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchFeatureFlags();
  }, [fetchFeatureFlags]);

  return {
    featureFlags,
    loading,
    error,
    fetchFeatureFlags,
    addFeatureFlag,
    editFeatureFlag,
    removeFeatureFlag
  };
} 