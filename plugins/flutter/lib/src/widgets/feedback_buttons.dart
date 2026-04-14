import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../state/chat_state.dart';
import '../models/chat_config.dart';
import '../models/chat_message.dart';

class FeedbackButtons extends StatefulWidget {
  final String messageId;
  final List<MessageFeedback>? existingFeedback;
  final GenAgentChatTheme? theme;

  const FeedbackButtons({
    super.key,
    required this.messageId,
    this.existingFeedback,
    this.theme,
  });

  @override
  State<FeedbackButtons> createState() => _FeedbackButtonsState();
}

class _FeedbackButtonsState extends State<FeedbackButtons> {
  String? _submittedFeedback;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    // Check if feedback already exists.
    if (widget.existingFeedback != null &&
        widget.existingFeedback!.isNotEmpty) {
      _submittedFeedback = widget.existingFeedback!.first.feedback;
    }
  }

  Future<void> _submitFeedback(String feedback) async {
    if (_submittedFeedback != null || _isSubmitting) return;

    setState(() => _isSubmitting = true);

    try {
      final chatState = context.read<ChatState>();
      await chatState.addFeedback(widget.messageId, feedback);
      if (mounted) {
        setState(() {
          _submittedFeedback = feedback;
          _isSubmitting = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() => _isSubmitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final primaryColor = widget.theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor;
    final isDisabled = _submittedFeedback != null || _isSubmitting;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _buildButton(
          icon: Icons.thumb_up_outlined,
          activeIcon: Icons.thumb_up,
          feedback: 'good',
          isActive: _submittedFeedback == 'good',
          isDisabled: isDisabled,
          activeColor: primaryColor,
          tooltip: 'Helpful',
        ),
        const SizedBox(width: 4),
        _buildButton(
          icon: Icons.thumb_down_outlined,
          activeIcon: Icons.thumb_down,
          feedback: 'bad',
          isActive: _submittedFeedback == 'bad',
          isDisabled: isDisabled,
          activeColor: Colors.red[400]!,
          tooltip: 'Not helpful',
        ),
      ],
    );
  }

  Widget _buildButton({
    required IconData icon,
    required IconData activeIcon,
    required String feedback,
    required bool isActive,
    required bool isDisabled,
    required Color activeColor,
    required String tooltip,
  }) {
    return SizedBox(
      width: 28,
      height: 28,
      child: IconButton(
        onPressed:
            isDisabled && !isActive ? null : () => _submitFeedback(feedback),
        padding: EdgeInsets.zero,
        iconSize: 16,
        tooltip: tooltip,
        icon: Icon(
          isActive ? activeIcon : icon,
          color: isActive
              ? activeColor
              : isDisabled
                  ? Colors.grey[350]
                  : Colors.grey[500],
        ),
      ),
    );
  }
}
