import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../state/chat_state.dart';
import '../models/chat_config.dart';
import 'chat_message_bubble.dart';
import 'welcome_card.dart';
import 'typing_indicator.dart';

class ChatMessageList extends StatefulWidget {
  final String? agentName;
  final GenAgentChatTheme? theme;
  final bool showWelcomeBeforeStart;
  final String? language;

  const ChatMessageList({
    super.key,
    this.agentName,
    this.theme,
    this.showWelcomeBeforeStart = true,
    this.language,
  });

  @override
  State<ChatMessageList> createState() => _ChatMessageListState();
}

class _ChatMessageListState extends State<ChatMessageList> {
  final ScrollController _scrollController = ScrollController();
  int _previousItemCount = 0;
  bool _previousTyping = false;

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final chatState = context.watch<ChatState>();
    final messages = chatState.messages;
    final isAgentTyping = chatState.isAgentTyping;
    final conversationId = chatState.conversationId;
    final hasWelcomeData = chatState.welcomeTitle != null ||
        chatState.welcomeMessage != null ||
        chatState.possibleQueries.isNotEmpty;

    final showWelcome = widget.showWelcomeBeforeStart &&
        conversationId == null &&
        hasWelcomeData;

    final itemCount = messages.length + (showWelcome ? 1 : 0) + (isAgentTyping ? 1 : 0);

    // Only auto-scroll when item count changes or typing state changes.
    if (itemCount != _previousItemCount || isAgentTyping != _previousTyping) {
      _previousItemCount = itemCount;
      _previousTyping = isAgentTyping;
      _scrollToBottom();
    }

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      itemCount: itemCount,
      itemBuilder: (context, index) {
        // Welcome card at the top.
        if (showWelcome && index == 0) {
          return WelcomeCard(
            title: chatState.welcomeTitle,
            message: chatState.welcomeMessage,
            imageUrl: chatState.welcomeImageUrl,
            possibleQueries: chatState.possibleQueries,
            theme: widget.theme,
            language: widget.language,
          );
        }

        final messageIndex = showWelcome ? index - 1 : index;

        // Typing indicator at the bottom.
        if (messageIndex >= messages.length) {
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: TypingIndicator(
              theme: widget.theme,
              thinkingPhrases: chatState.thinkingPhrases,
              thinkingDelayMs: chatState.thinkingDelayMs,
            ),
          );
        }

        final message = messages[messageIndex];
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: ChatMessageBubble(
            message: message,
            agentName: widget.agentName,
            theme: widget.theme,
            language: widget.language,
          ),
        );
      },
    );
  }
}
