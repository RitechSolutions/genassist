import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../state/chat_state.dart';
import '../models/chat_config.dart';
import '../models/interactive_content.dart';
import 'markdown_message.dart';
import 'file_type_icon.dart';

class InteractiveContentWidget extends StatelessWidget {
  final List<ChatContentBlock> blocks;
  final GenAgentChatTheme? theme;
  final bool hideOptions;
  final void Function(String option)? onOptionTap;

  const InteractiveContentWidget({
    super.key,
    required this.blocks,
    this.theme,
    this.hideOptions = false,
    this.onOptionTap,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: blocks.map((block) => _buildBlock(context, block)).toList(),
    );
  }

  Widget _buildBlock(BuildContext context, ChatContentBlock block) {
    switch (block) {
      case TextBlock(:final text):
        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: MarkdownMessage(text: text, theme: theme),
        );
      case OptionsBlock(:final options):
        if (hideOptions) return const SizedBox.shrink();
        return _buildOptions(context, options);
      case ItemsBlock(:final items):
        return _buildItems(context, items);
      case ScheduleBlock(:final schedule):
        return _buildSchedule(context, schedule);
      case FileBlock(:final data):
        return _buildFileCard(context, data);
    }
  }

  Widget _buildOptions(BuildContext context, List<String> options) {
    final chatState = context.read<ChatState>();
    final primaryColor = theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor;

    return Padding(
      padding: const EdgeInsets.only(top: 8, bottom: 4),
      child: Wrap(
        spacing: 8,
        runSpacing: 10,
        children: options.map((option) {
          return ElevatedButton(
            onPressed: () {
              if (onOptionTap != null) {
                onOptionTap!(option);
              } else {
                chatState.sendMessage(option);
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: primaryColor,
              foregroundColor: Colors.white,
              elevation: 0,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              minimumSize: const Size(0, 0),
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: Text(
              option,
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                fontFamily: theme?.fontFamily,
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildItems(BuildContext context, List<DynamicChatItem> items) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: items.map((item) => _buildItemCard(context, item)).toList(),
    );
  }

  Widget _buildItemCard(BuildContext context, DynamicChatItem item) {
    final primaryColor = theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.grey[300]!),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (item.image != null && item.image!.isNotEmpty)
            ClipRRect(
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(12)),
              child: Image.network(
                item.image!,
                width: double.infinity,
                height: 120,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => const SizedBox.shrink(),
              ),
            ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.name,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    fontFamily: theme?.fontFamily,
                  ),
                ),
                if (item.description != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    item.description!,
                    style: TextStyle(
                      fontSize: 13,
                      color: Colors.grey[600],
                      fontFamily: theme?.fontFamily,
                    ),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
                if (item.category != null) ...[
                  const SizedBox(height: 6),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: primaryColor.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      item.category!,
                      style: TextStyle(
                        fontSize: 11,
                        color: primaryColor,
                        fontFamily: theme?.fontFamily,
                      ),
                    ),
                  ),
                ],
                if (item.slots != null && item.slots!.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: item.slots!.map((slot) {
                      final isSelected = item.selectedSlot == slot;
                      return ChoiceChip(
                        label: Text(
                          slot,
                          style: TextStyle(
                            fontSize: 12,
                            color: isSelected ? Colors.white : primaryColor,
                            fontFamily: theme?.fontFamily,
                          ),
                        ),
                        selected: isSelected,
                        selectedColor: primaryColor,
                        backgroundColor: Colors.white,
                        side: BorderSide(
                          color: primaryColor.withOpacity(0.4),
                        ),
                        onSelected: (_) {
                          final chatState = context.read<ChatState>();
                          chatState.sendMessage(slot);
                        },
                      );
                    }).toList(),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSchedule(BuildContext context, ScheduleItem schedule) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.grey[300]!),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (schedule.title != null) ...[
            Text(
              schedule.title!,
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                fontFamily: theme?.fontFamily,
              ),
            ),
            const SizedBox(height: 8),
          ],
          ...schedule.restaurants
              .map((item) => _buildItemCard(context, item)),
        ],
      ),
    );
  }

  Widget _buildFileCard(BuildContext context, FileItem data) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        onTap: () async {
          final uri = Uri.tryParse(data.url);
          if (uri != null && await canLaunchUrl(uri)) {
            await launchUrl(uri, mode: LaunchMode.externalApplication);
          }
        },
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            border: Border.all(color: Colors.grey[300]!),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            children: [
              FileTypeIcon(mimeType: data.type, size: 32),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      data.name,
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                        fontFamily: theme?.fontFamily,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      data.type,
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey[500],
                        fontFamily: theme?.fontFamily,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.download_rounded,
                color: Colors.grey[500],
                size: 20,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
