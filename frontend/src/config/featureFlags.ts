/**
 * Constants for feature flag keys, following the hierarchical structure
 * Used to maintain consistency when referencing feature flags throughout the app
 */
export const FeatureFlags = {
    // UI related feature flags
    UI: {
      MENU: 'ui.menu',
      SIDEBAR: 'ui.sidebar',
      SETTINGS: 'ui.settings',
      NOTIFICATIONS: 'ui.notifications',
      AGENTS: 'ui.agents',
    },
    
    // Feature specific flags
    FEATURE: {
      USER_TYPES: 'feature.userTypes',
      ROLES: 'feature.roles',
      ANALYTICS: 'feature.analytics',
      API_KEYS: 'feature.apiKeys'
    },

    ADMIN_TOOLS: {
      APP_SETTINGS: 'ui.menu.app-settings',
    },
  
    // Specific UI components within features
    COMPONENTS: {
      CHAT: 'components.chat',
      KNOWLEDGE_BASE: 'components.knowledgeBase',
      TOOLS: 'components.tools',
    }
  };
  
  /**
   * Helper function to get a nested feature flag key
   * Example: getFeatureFlagKey(FeatureFlags.UI.MENU, 'userTypes')
   * Returns: 'ui.menu.userTypes'
   */
  export function getFeatureFlagKey(prefix: string, suffix: string): string {
    return `${prefix}.${suffix}`;
  }
  
  /**
   * For menu items specifically
   */
  export function getMenuItemKey(itemKey: string): string {
    return getFeatureFlagKey(FeatureFlags.UI.MENU, itemKey);
  } 