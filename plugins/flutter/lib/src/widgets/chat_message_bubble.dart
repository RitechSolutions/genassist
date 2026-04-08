import 'package:flutter/material.dart';
import '../models/chat_config.dart';
import '../models/chat_message.dart';
import '../models/interactive_content.dart';
import '../utils/interactive_content_parser.dart';
import '../utils/time_utils.dart';
import 'markdown_message.dart';
import 'interactive_content_widget.dart';
import 'feedback_buttons.dart';
import 'file_type_icon.dart';

class ChatMessageBubble extends StatelessWidget {
  final ChatMessage message;
  final String? agentName;
  final GenAgentChatTheme? theme;
  final String? language;

  const ChatMessageBubble({
    super.key,
    required this.message,
    this.agentName,
    this.theme,
    this.language,
  });

  @override
  Widget build(BuildContext context) {
    switch (message.speaker) {
      case Speaker.agent:
        return _buildAgentBubble(context);
      case Speaker.customer:
        return _buildCustomerBubble(context);
      case Speaker.special:
        return _buildSpecialBubble(context);
    }
  }

  Widget _buildAgentBubble(BuildContext context) {
    final contentBlocks = parseInteractiveContentBlocks(
      message.text,
      messageType: message.type,
    );

    final hasInteractiveContent = contentBlocks.any(
      (block) => block is! TextBlock,
    );

    return Align(
      alignment: Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.78,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(left: 4, bottom: 4),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    agentName ?? 'Agent',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: theme?.textColor?.withOpacity(0.6) ??
                          Colors.black54,
                      fontFamily: theme?.fontFamily,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    formatTimestamp(message.createTime, language: language),
                    style: TextStyle(
                      fontSize: 11,
                      color: Colors.grey[500],
                      fontFamily: theme?.fontFamily,
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.only(left: 4, right: 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (hasInteractiveContent)
                    InteractiveContentWidget(
                      blocks: contentBlocks,
                      theme: theme,
                    )
                  else
                    MarkdownMessage(text: message.text, theme: theme),
                  if (message.attachments != null &&
                      message.attachments!.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    _buildAttachments(message.attachments!),
                  ],
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.only(left: 4, top: 4),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (message.messageId != null)
                    FeedbackButtons(
                      messageId: message.messageId!,
                      existingFeedback: message.feedback,
                      theme: theme,
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCustomerBubble(BuildContext context) {
    final primaryColor = theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor;

    return Align(
      alignment: Alignment.centerRight,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.78,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Padding(
              padding: const EdgeInsets.only(right: 4, bottom: 4),
              child: Text(
                formatTimestamp(message.createTime, language: language),
                style: TextStyle(
                  fontSize: 11,
                  color: Colors.grey[500],
                  fontFamily: theme?.fontFamily,
                ),
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: primaryColor,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(16),
                  topRight: Radius.circular(4),
                  bottomLeft: Radius.circular(16),
                  bottomRight: Radius.circular(16),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    message.text,
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: theme?.fontSize ?? 14,
                      fontFamily: theme?.fontFamily,
                    ),
                  ),
                  if (message.attachments != null &&
                      message.attachments!.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    _buildAttachments(message.attachments!),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSpecialBubble(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: Colors.grey[200],
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            message.text,
            style: TextStyle(
              fontSize: 13,
              color: Colors.grey[600],
              fontStyle: FontStyle.italic,
              fontFamily: theme?.fontFamily,
            ),
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }

  Widget _buildAttachments(List<Attachment> attachments) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: attachments.map((attachment) {
        final isImage = attachment.type.startsWith('image/');
        if (isImage) {
          return ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: Image.network(
              attachment.url,
              width: 150,
              height: 120,
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) => _buildFileChip(attachment),
            ),
          );
        }
        return _buildFileChip(attachment);
      }).toList(),
    );
  }

  Widget _buildFileChip(Attachment attachment) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.2),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey[300]!),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          FileTypeIcon(mimeType: attachment.type, size: 18),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              attachment.name,
              style: const TextStyle(fontSize: 12),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}
