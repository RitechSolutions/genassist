import { FeatureFlag, ParsedFeatureFlag, FeatureToggleAttribute } from "@/interfaces/featureFlag.interface";

/**
 * Parse feature flags with attribute and hierarchical structure
 * @param featureFlags The raw feature flags from the API
 * @param prefix Optional prefix to filter flags by (e.g., 'ui.menu')
 * @returns Array of parsed feature flags
 */
export const parseFeatureFlags = (featureFlags: FeatureFlag[], prefix: string = ''): ParsedFeatureFlag[] => {
  // Filter flags that start with the prefix
  const filteredFlags = featureFlags.filter(flag => 
    !prefix || flag.key.startsWith(prefix)
  ).filter(flag => flag.is_active);

  // Group flags by their base key
  const flagsMap: Record<string, ParsedFeatureFlag> = {};

  filteredFlags.forEach(flag => {
    // Extract the specific feature name from the hierarchical key
    let itemName = flag.key;
    
    if (prefix && flag.key.startsWith(prefix)) {
      // If the key matches the prefix exactly, use the last part after the dot
      if (flag.key === prefix) {
        itemName = flag.key.substring(flag.key.lastIndexOf('.') + 1);
      } else {
        // Otherwise, extract the part after the prefix
        itemName = flag.key.substring(prefix.length + 1);
      }
      
      // If there are additional dots, only take the first segment
      if (itemName.includes('.')) {
        itemName = itemName.split('.')[0];
      }
    }

    // Initialize or reuse the flag group
    const item = flagsMap[itemName] || { 
      itemName,
      fullKey: flag.key 
    };

    // Parse the value based on the attribute type
    if (flag.attribute) {
      switch (flag.attribute) {
        case FeatureToggleAttribute.VISIBLE:
          item.visible = flag.value === 'true';
          break;
        case FeatureToggleAttribute.DISABLED:
          item.disabled = flag.value === 'true';
          break;
        case FeatureToggleAttribute.VARIANT:
          item.variant = flag.value;
          break;
      }
    } else {
      // For backward compatibility with the current implementation
      item.visible = flag.value === 'true';
    }

    flagsMap[itemName] = item;
  });

  return Object.values(flagsMap);
};

/**
 * Check if a feature flag is enabled based on hierarchy
 * @param featureFlags The raw feature flags 
 * @param key The feature flag key to check
 * @returns boolean indicating if the feature is enabled
 */
export const isFeatureEnabled = (featureFlags: FeatureFlag[], key: string): boolean => {
  const parts = key.split('.');
  
  // Try exact match first
  const exactFlag = featureFlags.find(f => f.key === key && f.is_active);
  if (exactFlag) {
    // If it has an attribute, handle it accordingly
    if (exactFlag.attribute === FeatureToggleAttribute.VISIBLE) {
      return exactFlag.value === 'true';
    }
    if (exactFlag.attribute === FeatureToggleAttribute.DISABLED) {
      return exactFlag.value !== 'true';
    }
    // Default behavior
    return exactFlag.value === 'true';
  }

  // Check for parent keys for hierarchical fallback
  for (let i = parts.length - 1; i > 0; i--) {
    const parentKey = parts.slice(0, i).join('.');
    const parentFlag = featureFlags.find(f => f.key === parentKey && f.is_active);
    
    if (parentFlag) {
      if (parentFlag.attribute === FeatureToggleAttribute.VISIBLE) {
        return parentFlag.value === 'true';
      }
      if (parentFlag.attribute === FeatureToggleAttribute.DISABLED) {
        return parentFlag.value !== 'true';
      }
      return parentFlag.value === 'true';
    }
  }

  // Default to true if no matching flag found
  return true;
};

/**
 * Get the value of a feature flag based on hierarchy
 * @param featureFlags The raw feature flags
 * @param key The feature flag key to check
 * @returns The value of the feature flag or null
 */
export const getFeatureValue = (featureFlags: FeatureFlag[], key: string): string | null => {
  const parts = key.split('.');
  
  // Try exact match first
  const exactFlag = featureFlags.find(f => f.key === key && f.is_active);
  if (exactFlag) {
    return exactFlag.value;
  }

  // Check for parent keys for hierarchical fallback
  for (let i = parts.length - 1; i > 0; i--) {
    const parentKey = parts.slice(0, i).join('.');
    const parentFlag = featureFlags.find(f => f.key === parentKey && f.is_active);
    
    if (parentFlag) {
      return parentFlag.value;
    }
  }

  return null;
}; 