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
      API_KEYS: 'feature.apiKeys',
      TEMPLATE_MARKETPLACE: 'feature.templateMarketplace'
    },

    // Analytics / agent metrics: cost is hidden by default; show when this flag is enabled
    ANALYTICS: {
      SHOW_COST_PER_CONVERSATION: 'analytics.showCostPerConversation',
    },

    // Conversations dialog: the "Ask GenAI" assistant is hidden by default; show when this flag is enabled
    CONVERSATIONS: {
      SHOW_ASK_GENAI: 'conversations.showAskGenAI',
    },

    LLM_SETTINGS: {
      SHOW_LOCAL_FINE_TUNE: 'llmSettings.showLocalFineTune',
      SHOW_BEDROCK_FINE_TUNE: 'llmSettings.showBedrockFineTune',
    },

    // Workflow specific flags
    WORKFLOW: {
      CHAT_INPUT: 'workflow.chatInput',
      CONVERSATIONAL_TAB: 'workflow.conversationalTab',
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