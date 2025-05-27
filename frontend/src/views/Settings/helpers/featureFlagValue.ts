import { getFeatureFlags } from "@/services/featureFlags";

export const isFeatureEnabled = async (key: string): Promise<boolean> => {
    try {
      const flags = await getFeatureFlags();
      const flag = flags.find(f => f.key === key && f.is_active === 1);
      return flag?.val === "true";
    } catch (error) {
      console.error("Error checking feature flag:", error);
      return false;
    }
  };
  
  export const getFeatureValue = async (key: string): Promise<string | null> => {
    try {
      const flags = await getFeatureFlags();
      const flag = flags.find(f => f.key === key && f.is_active === 1);
      return flag ? flag.val : null;
    } catch (error) {
      console.error("Error getting feature flag value:", error);
      return null;
    }
  }; 