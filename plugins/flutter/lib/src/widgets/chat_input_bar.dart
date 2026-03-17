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
    final isDisabled = chatState.isTakenOver || chatState.isFinalized;
    final primaryColor = widget.theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor;

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
          padding: const EdgeInsets.fromLTRB(8, 8, 8, 8),
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
                // File picker button.
                if (widget.useFile)
                  IconButton(
                    onPressed: isDisabled ? null : _pickFiles,
                    icon: Icon(
                      Icons.attach_file,
                      color: isDisabled ? Colors.grey[400] : primaryColor,
                    ),
                    tooltip: 'Attach file',
                  ),

                // Text input field.
                Expanded(
                  child: TextField(
                    controller: _controller,
                    focusNode: _focusNode,
                    enabled: !isDisabled,
                    maxLines: 4,
                    minLines: 1,
                    textInputAction: TextInputAction.send,
                    style: TextStyle(
                      fontSize: widget.theme?.fontSize ?? 14,
                      fontFamily: widget.theme?.fontFamily,
                      color: widget.theme?.textColor,
                    ),
                    decoration: InputDecoration(
                      hintText: widget.placeholder ??
                          getTranslationString(
                            'input.placeholder',
                            defaultTranslations,
                            fallback: 'Ask a question',
                          ),
                      hintStyle: TextStyle(
                        color: Colors.grey[400],
                        fontFamily: widget.theme?.fontFamily,
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 14,
                        vertical: 10,
                      ),
                      filled: true,
                      fillColor: Colors.grey[100],
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
                          color: primaryColor.withOpacity(0.5),
                        ),
                      ),
                    ),
                    onSubmitted: isDisabled
                        ? null
                        : (_) => _handleSend(chatState),
                  ),
                ),

                const SizedBox(width: 4),

                // Voice input button.
                if (widget.useAudio)
                  VoiceInputButton(
                    onResult: (text) {
                      _controller.text = text;
                      _focusNode.requestFocus();
                    },
                    theme: widget.theme,
                    enabled: !isDisabled,
                  ),

                // Send button.
                IconButton(
                  onPressed: isDisabled
                      ? null
                      : () => _handleSend(chatState),
                  icon: Icon(
                    Icons.send_rounded,
                    color: isDisabled ? Colors.grey[400] : primaryColor,
                  ),
                  tooltip: 'Send',
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
