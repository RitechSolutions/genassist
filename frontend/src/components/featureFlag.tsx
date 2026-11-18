import React, { ReactNode } from 'react';
import { useFeatureFlag } from '@/context/FeatureFlagContext';
import { FeatureToggleAttribute } from '@/interfaces/featureFlag.interface';

interface FeatureFlagProps {
  /** The feature flag key to check (e.g., "ui.menu.reports") */
  flagKey: string;
  /** The attribute to check for (defaults to VISIBLE) */
  attribute?: FeatureToggleAttribute;
  /** The children to render if the feature is enabled */
  children: ReactNode;
  /** Optional fallback to render if feature is disabled */
  fallback?: ReactNode;
}

/**
 * Renders its children unless the given feature flag hides or disables them
 * (then `fallback` is rendered). Content is shown when no matching flag exists.
 */
export function FeatureFlag({ 
  flagKey, 
  attribute = FeatureToggleAttribute.VISIBLE, 
  children, 
  fallback = null 
}: FeatureFlagProps) {
  const { flags } = useFeatureFlag();
  
  const featureItem = useFeatureFlag().getFeatureItem(flagKey);

  if (!featureItem) {
    // No feature flag found, default to showing the content
    return <>{children}</>;
  }

  // Check based on attribute type
  if (attribute === FeatureToggleAttribute.VISIBLE) {
    if (featureItem.visible === false) {
      return <>{fallback}</>;
    }
  } else if (attribute === FeatureToggleAttribute.DISABLED) {
    if (featureItem.disabled === true) {
      return <>{fallback}</>;
    }
  }

  return <>{children}</>;
}

interface FeatureFlagMenuItemProps {
  /** The menu item key (will be prefixed with ui.menu.) */
  itemKey: string;
  /** The children component to render if enabled */
  children: ReactNode;
  /** Optional fallback to render if feature is disabled */
  fallback?: ReactNode;
  /** Additional props to pass to the child component */
  [key: string]: unknown;
}

/**
 * Feature-flag wrapper for a sidebar menu item.
 */
export function FeatureFlagMenuItem({ 
  itemKey, 
  children, 
  fallback = null,
  ...rest 
}: FeatureFlagMenuItemProps) {
  // Use the full key format with ui.menu prefix
  const flagKey = `ui.menu.${itemKey}`;
  const featureItem = useFeatureFlag().getFeatureItem(flagKey);

  if (featureItem && featureItem.visible === false) {
    return <>{fallback}</>;
  }

  return React.isValidElement(children) 
    ? React.cloneElement(children as React.ReactElement, rest) 
    : <>{children}</>;
}

/**
 * Hook to check if a feature flag is visible. Returns false when the flag is missing.
 */
export function useFeatureFlagVisible(flagKey: string): boolean {
  const { getFeatureItem } = useFeatureFlag();
  const item = getFeatureItem(flagKey);
  return item?.visible === true;
}

/**
 * Hook to check if variant matches specified value
 */
export function useFeatureVariant(flagKey: string, expectedVariant: string): boolean {
  const { getFeatureItem } = useFeatureFlag();
  const item = getFeatureItem(flagKey);
  return item?.variant === expectedVariant;
} 