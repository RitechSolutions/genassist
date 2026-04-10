import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/chat_config.dart';
import '../models/chat_message.dart';
import '../models/interactive_content.dart';
import '../state/chat_state.dart';
import '../utils/interactive_content_parser.dart';
import '../utils/time_utils.dart';
import 'markdown_message.dart';
import 'interactive_content_widget.dart';
import 'feedback_buttons.dart';
import 'file_type_icon.dart';

final Set<String> _consumedQuickActionMessageKeys = <String>{};

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
    final messageKey = message.messageId ?? message.createTime.toStringAsFixed(3);
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
                      hideOptions: _consumedQuickActionMessageKeys.contains(messageKey),
                      onOptionTap: (option) {
                        _consumedQuickActionMessageKeys.add(messageKey);
                        context.read<ChatState>().sendMessage(option);
                      },
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
    final hasAttachments =
        message.attachments != null && message.attachments!.isNotEmpty;
    final hasText = message.text.trim().isNotEmpty;

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
            if (hasAttachments)
              Padding(
                padding: const EdgeInsets.only(right: 2, bottom: 8),
                child: _buildCustomerAttachmentPanel(message.attachments!),
              ),
            if (hasText)
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
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCustomerAttachmentPanel(List<Attachment> attachments) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: attachments.map((attachment) {
        final mime = attachment.type.isNotEmpty
            ? attachment.type
            : mimeFromExtension(attachment.name.split('.').last);
        final isPdf = mime.contains('pdf');
        final isImage = mime.startsWith('image/');
        final accentColor = isPdf
            ? const Color(0xFFCC0000)
            : isImage
                ? const Color(0xFF2563EB)
                : const Color(0xFF6B7280);
        final ext = attachment.name.contains('.')
            ? attachment.name.split('.').last.toUpperCase()
            : 'FILE';
        return Container(
          margin: const EdgeInsets.only(bottom: 6),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: Colors.transparent,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: accentColor.withValues(alpha: 0.65)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: accentColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: accentColor.withValues(alpha: 0.5)),
                ),
                child: Icon(
                  Icons.description_outlined,
                  size: 18,
                  color: accentColor,
                ),
              ),
              const SizedBox(width: 10),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 200),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      attachment.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: const Color(0xFF1F2937),
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        fontFamily: theme?.fontFamily,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      ext.isNotEmpty ? ext : mime.toUpperCase(),
                      style: TextStyle(
                        color: accentColor,
                        fontSize: 12,
                        fontFamily: theme?.fontFamily,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }

  Widget _buildSpecialBubble(BuildContext context) {
    final isTakeover = message.type == 'takeover' ||
        message.text.toLowerCase().contains('supervisor took over');
    final isFinalized = message.type == 'finalized' ||
        message.text.toLowerCase().contains('conversation finalized');
    final isStatusBadge = isTakeover || isFinalized;
    final badgeBg = isTakeover
        ? const Color(0xFFFFF4E5)
        : const Color(0xFFEFF8FF);
    final badgeBorder = isTakeover
        ? const Color(0xFFFDB022)
        : const Color(0xFF84CAFF);
    final badgeText = isTakeover
        ? const Color(0xFF7A2E0D)
        : const Color(0xFF175CD3);
    final badgeIcon = isTakeover ? Icons.support_agent : Icons.check_circle_outline;

    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: isStatusBadge ? badgeBg : Colors.grey[200],
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isStatusBadge ? badgeBorder : Colors.transparent,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (isStatusBadge) ...[
                Icon(
                  badgeIcon,
                  size: 14,
                  color: badgeText,
                ),
                const SizedBox(width: 6),
              ],
              Flexible(
                child: Text(
                  message.text,
                  style: TextStyle(
                    fontSize: isStatusBadge ? 13 : 12,
                    color: isStatusBadge ? badgeText : Colors.grey[700],
                    fontWeight: isStatusBadge ? FontWeight.w600 : FontWeight.w500,
                    fontStyle: isStatusBadge ? FontStyle.normal : FontStyle.italic,
                    fontFamily: theme?.fontFamily,
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
            ],
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
