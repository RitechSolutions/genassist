import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:file_picker/file_picker.dart';
import '../state/chat_state.dart';
import '../models/chat_config.dart';
import '../utils/i18n.dart';
import 'attachment_preview.dart';
import 'voice_input_button.dart';

class ChatInputBar extends StatefulWidget {
  final String? placeholder;
  final GenAgentChatTheme? theme;
  final bool useAudio;
  final bool useFile;
  final List<AllowedExtension>? allowedExtensions;
  final String formDisplay;

  const ChatInputBar({
    super.key,
    this.placeholder,
    this.theme,
    this.useAudio = false,
    this.useFile = false,
    this.allowedExtensions,
    this.formDisplay = 'footer',
  });

  @override
  State<ChatInputBar> createState() => _ChatInputBarState();
}

class _ChatInputBarState extends State<ChatInputBar> {
  final TextEditingController _controller = TextEditingController();
  final FocusNode _focusNode = FocusNode();
  final List<PlatformFile> _selectedFiles = [];

  bool get _hasInput => _controller.text.trim().isNotEmpty || _selectedFiles.isNotEmpty;

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _handleSend(ChatState chatState) {
    final text = _controller.text.trim();
    if (text.isEmpty && _selectedFiles.isEmpty) return;

    chatState.sendMessage(
      text,
      files: _selectedFiles.isNotEmpty ? _selectedFiles : null,
    );

    _controller.clear();
    setState(() => _selectedFiles.clear());
    _focusNode.requestFocus();
  }

  Future<void> _pickFiles() async {
    final allowedExts = widget.allowedExtensions
        ?.map(_extensionString)
        .where((e) => e.isNotEmpty)
        .toList();

    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: allowedExts != null && allowedExts.isNotEmpty
          ? FileType.custom
          : FileType.any,
      allowedExtensions: allowedExts,
    );

    if (result != null && result.files.isNotEmpty) {
      setState(() => _selectedFiles.addAll(result.files));
    }
  }

  void _removeFile(int index) {
    setState(() => _selectedFiles.removeAt(index));
  }

  String _extensionString(AllowedExtension ext) {
    switch (ext) {
      case AllowedExtension.imagePng:
        return 'png';
      case AllowedExtension.imageJpeg:
      case AllowedExtension.imageJpg:
        return 'jpg';
      case AllowedExtension.imageGif:
        return 'gif';
      case AllowedExtension.applicationPdf:
        return 'pdf';
      case AllowedExtension.applicationMsword:
        return 'doc';
      case AllowedExtension.applicationDocx:
        return 'docx';
      case AllowedExtension.imageAll:
        return '';
    }
  }


  @override
  Widget build(BuildContext context) {
    final chatState = context.watch<ChatState>();
    final isInputDisabled = chatState.isTakenOver || chatState.isFinalized;
    final isSendDisabled = isInputDisabled || chatState.isAgentTyping;
    final primaryColor = widget.theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor;
    final canSend = !isSendDisabled && _hasInput;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [

        // Attachment preview strip.
        if (_selectedFiles.isNotEmpty)
          AttachmentPreview(
            files: _selectedFiles,
            onRemove: _removeFile,
          ),

        // Input disclaimer.
        if (chatState.inputDisclaimerHtml != null)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Text(
              chatState.inputDisclaimerHtml!,
              style: TextStyle(
                fontSize: 11,
                color: Colors.grey[500],
                fontFamily: widget.theme?.fontFamily,
              ),
              textAlign: TextAlign.center,
            ),
          ),

        // Input bar.
        Container(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
          decoration: BoxDecoration(
            color: widget.theme?.backgroundColor ?? Colors.white,
            border: Border(
              top: BorderSide(color: Colors.grey[200]!),
            ),
          ),
          child: SafeArea(
            top: false,
            child: Row(
              children: [
                if (widget.useFile)
                  _buildActionCircle(
                    onTap: isInputDisabled ? null : _pickFiles,
                    icon: Icons.add,
                    tooltip: 'Attach file',
                    background: const Color(0xFFF4F4F8),
                    iconColor: isInputDisabled ? Colors.grey[400]! : const Color(0xFF8E8E93),
                  ),
                if (widget.useFile) const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    controller: _controller,
                    focusNode: _focusNode,
                    enabled: !isInputDisabled,
                    maxLines: 4,
                    minLines: 1,
                    textInputAction: TextInputAction.send,
                    style: TextStyle(
                      fontSize: widget.theme?.fontSize ?? 15,
                      fontFamily: widget.theme?.fontFamily,
                      color: widget.theme?.textColor ?? const Color(0xFF1F1F24),
                    ),
                    decoration: InputDecoration(
                      hintText: widget.placeholder ??
                          getTranslationString(
                            'input.placeholder',
                            defaultTranslations,
                            fallback: 'Ask a question',
                          ),
                      hintStyle: TextStyle(
                        color: const Color(0xFF9B9BA4),
                        fontFamily: widget.theme?.fontFamily,
                      ),
                      isDense: true,
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 14,
                        vertical: 10,
                      ),
                      filled: true,
                      fillColor: const Color(0xFFF4F4F8),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: BorderSide.none,
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: BorderSide.none,
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: BorderSide(
                          color: primaryColor.withValues(alpha: 0.35),
                        ),
                      ),
                    ),
                    onChanged: (_) => setState(() {}),
                    onSubmitted: canSend ? (_) => _handleSend(chatState) : null,
                  ),
                ),
                if (widget.useAudio) ...[
                  const SizedBox(width: 4),
                  VoiceInputButton(
                    onResult: (text) {
                      _controller.text = text;
                      setState(() {});
                      _focusNode.requestFocus();
                    },
                    theme: widget.theme,
                    enabled: !isInputDisabled,
                  ),
                ],
                const SizedBox(width: 4),
                _buildActionCircle(
                  onTap: canSend ? () => _handleSend(chatState) : null,
                  icon: Icons.send_rounded,
                  tooltip: 'Send',
                  background: canSend ? const Color(0xFFCC0000) : const Color(0xFFE7E7EC),
                  iconColor: canSend ? Colors.white : const Color(0xFF9F9FA8),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildActionCircle({
    required VoidCallback? onTap,
    required IconData icon,
    required String tooltip,
    required Color background,
    required Color iconColor,
  }) {
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: background,
            shape: BoxShape.circle,
          ),
          alignment: Alignment.center,
          child: Icon(icon, size: 18, color: iconColor),
        ),
      ),
    );
  }
}
