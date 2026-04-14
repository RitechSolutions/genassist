/// GenAssist Chat - A Flutter chat widget for GenAssist AI agents.
///
/// Provides a customizable chat widget with WebSocket support, file uploads,
/// voice input, internationalization, and more.
library gen_agent_chat;

// Main widget
export 'src/widgets/gen_agent_chat.dart' show GenAgentChat;

// Models
export 'src/models/chat_message.dart'
    show ChatMessage, Attachment, MessageFeedback, Speaker;
export 'src/models/chat_config.dart'
    show
        GenAgentChatTheme,
        ChatMode,
        FloatingConfig,
        FloatingPosition,
        AllowedExtension,
        mimeFromExtension,
        isImageExtension;
export 'src/models/interactive_content.dart'
    show
        ChatContentBlock,
        TextBlock,
        ItemsBlock,
        ScheduleBlock,
        OptionsBlock,
        FileBlock,
        DynamicChatItem,
        ScheduleItem,
        FileItem;
export 'src/models/api_responses.dart'
    show AgentWelcomeData, AgentThinkingConfig;

// Services
export 'src/services/chat_service.dart' show ChatService;

// State
export 'src/state/chat_state.dart' show ChatState;

// Utilities
export 'src/utils/i18n.dart'
    show
        Translations,
        resolveLanguage,
        mergeTranslations,
        getTranslationsForLanguage,
        getTranslationString,
        getTranslationArray,
        defaultTranslations;
export 'src/utils/interactive_content_parser.dart'
    show parseInteractiveContentBlocks, generateMessageContent;

// Additional widgets
export 'src/widgets/chat_bubble.dart' show ChatBubble;
