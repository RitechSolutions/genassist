export interface FeatureFlag {
    id?: string;
    key: string;
    val: string;
    description: string;
    is_active: number;
    created_at?: string;
    updated_at?: string;
    attribute?: FeatureToggleAttribute;
  }
  
  export enum FeatureToggleAttribute {
    VISIBLE = 'visible',
    DISABLED = 'disabled',
    VARIANT = 'variant'
  }
  
  export interface FeatureFlagFormData {
    id?: string;
    key: string;
    val: string;
    description: string;
    is_active: number;
    attribute?: FeatureToggleAttribute;
  }
  
  export interface ParsedFeatureFlag {
    itemName: string;
    fullKey: string;
    visible?: boolean;
    disabled?: boolean;
    variant?: string;
  } 