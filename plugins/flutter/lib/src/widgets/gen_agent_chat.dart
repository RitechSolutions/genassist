import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../state/chat_state.dart';
import '../models/chat_config.dart';
import '../utils/i18n.dart';
import 'chat_header.dart';
import 'chat_message_list.dart';
import 'chat_input_bar.dart';
import 'chat_bubble.dart';

class GenAgentChat extends StatefulWidget {
  final String url;
  final String? websocketUrl;
  final String apiKey;
  final String? tenant;
  final Map<String, dynamic>? metadata;
  final GenAgentChatTheme? theme;
  final String headerTitle;
  final String? description;
  final String? placeholder;
  final String? agentName;
  final String? logoUrl;
  final ChatMode mode;
  final FloatingConfig? floatingConfig;
  final String? language;
  final Map<String, dynamic>? translations;
  final bool useWs;
  final bool usePoll;
  final bool useAudio;
  final bool useFile;
  final List<AllowedExtension>? allowedExtensions;
  final String? reCaptchaKey;
  final bool widget;
  final void Function(Object)? onError;
  final VoidCallback? onTakeover;
  final VoidCallback? onFinalize;
  final void Function(Map<String, dynamic>)? onConfigLoaded;
  final String formDisplay;
  final bool showWelcomeBeforeStart;
  final bool noColorAnimation;
  final String? serverUnavailableMessage;
  final String? serverUnavailableContactUrl;
  final String? serverUnavailableContactLabel;
  final VoidCallback? onClose;

  const GenAgentChat({
    super.key,
    required this.url,
    required this.apiKey,
    this.websocketUrl,
    this.tenant,
    this.metadata,
    this.theme,
    this.headerTitle = 'Genassist',
    this.description,
    this.placeholder,
    this.agentName,
    this.logoUrl,
    this.mode = ChatMode.embedded,
    this.floatingConfig,
    this.language,
    this.translations,
    this.useWs = true,
    this.usePoll = false,
    this.useAudio = false,
    this.useFile = false,
    this.allowedExtensions,
    this.reCaptchaKey,
    this.widget = false,
    this.onError,
    this.onTakeover,
    this.onFinalize,
    this.onConfigLoaded,
    this.formDisplay = 'footer',
    this.showWelcomeBeforeStart = true,
    this.noColorAnimation = false,
    this.serverUnavailableMessage,
    this.serverUnavailableContactUrl,
    this.serverUnavailableContactLabel,
    this.onClose,
  });

  @override
  State<GenAgentChat> createState() => _GenAgentChatState();
}

class _GenAgentChatState extends State<GenAgentChat> {
  late ChatState _chatState;
  bool _isFloatingOpen = false;

  @override
  void initState() {
    super.initState();
    _chatState = ChatState(
      baseUrl: widget.url,
      websocketUrl: widget.websocketUrl,
      apiKey: widget.apiKey,
      tenant: widget.tenant,
      metadata: widget.metadata,
      language: widget.language,
      useWs: widget.useWs,
      usePoll: widget.usePoll,
      onError: widget.onError,
      onTakeover: widget.onTakeover,
      onFinalize: widget.onFinalize,
      onConfigLoaded: widget.onConfigLoaded != null
          ? (meta) { if (meta != null) widget.onConfigLoaded!(meta); }
          : null,
      serverUnavailableMessage: widget.serverUnavailableMessage,
      serverUnavailableContactUrl: widget.serverUnavailableContactUrl,
      serverUnavailableContactLabel: widget.serverUnavailableContactLabel,
    );
    _chatState.init();
  }

  @override
  void dispose() {
    _chatState.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider.value(
      value: _chatState,
      child: _buildForMode(),
    );
  }

  Widget _buildForMode() {
    switch (widget.mode) {
      case ChatMode.floating:
        return _buildFloatingMode();
      case ChatMode.fullscreen:
        return _buildChatContent(fullscreen: true);
      case ChatMode.embedded:
        return _buildChatContent();
    }
  }

  Widget _buildFloatingMode() {
    return Stack(
      fit: StackFit.expand,
      children: [
        Positioned(
          bottom: 16,
          right: 16,
          child: ChatBubble(
            isOpen: _isFloatingOpen,
            onToggle: _toggleFloating,
            config: widget.floatingConfig,
            theme: widget.theme,
          ),
        ),
      ],
    );
  }

  Future<void> _toggleFloating() async {
    if (_isFloatingOpen) {
      if (Navigator.of(context).canPop()) {
        Navigator.of(context).pop();
      }
      return;
    }
    setState(() => _isFloatingOpen = true);
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        fullscreenDialog: true,
        builder: (ctx) => ChangeNotifierProvider.value(
          value: _chatState,
          child: Scaffold(
            backgroundColor: widget.theme?.backgroundColor ?? Colors.white,
            body: _buildChatContent(
              fullscreen: true,
              onClose: () => Navigator.of(ctx).pop(),
            ),
          ),
        ),
      ),
    );
    if (mounted) {
      setState(() => _isFloatingOpen = false);
      widget.onClose?.call();
    }
  }

  Widget _buildChatContent({
    bool fullscreen = false,
    VoidCallback? onClose,
  }) {
    final theme = widget.theme;
    final effectiveOnClose = onClose ?? widget.onClose;
    return Container(
      decoration: BoxDecoration(
        color: theme?.backgroundColor ?? Colors.white,
        borderRadius: fullscreen ? null : BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          ChatHeader(
            title: widget.headerTitle,
            description: widget.description,
            agentName: widget.agentName,
            logoUrl: widget.logoUrl,
            theme: widget.theme,
            noColorAnimation: widget.noColorAnimation,
            onClose: effectiveOnClose,
          ),
          Expanded(
            child: ChatMessageList(
              agentName: widget.agentName,
              theme: widget.theme,
              showWelcomeBeforeStart: widget.showWelcomeBeforeStart,
              language: widget.language,
            ),
          ),
          ChatInputBar(
            placeholder: widget.placeholder,
            theme: widget.theme,
            useAudio: widget.useAudio,
            useFile: widget.useFile,
            allowedExtensions: widget.allowedExtensions,
            formDisplay: widget.formDisplay,
          ),
        ],
      ),
    );
  }
}
