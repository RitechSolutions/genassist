import 'dart:io';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import '../models/chat_config.dart';
import 'file_type_icon.dart';

class AttachmentPreview extends StatelessWidget {
  final List<PlatformFile> files;
  final void Function(int index) onRemove;

  const AttachmentPreview({
    super.key,
    required this.files,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    if (files.isEmpty) return const SizedBox.shrink();

    return Container(
      height: 80,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.grey[50],
        border: Border(top: BorderSide(color: Colors.grey[200]!)),
      ),
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: files.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final file = files[index];
          return _buildFilePreview(file, index);
        },
      ),
    );
  }

  Widget _buildFilePreview(PlatformFile file, int index) {
    final isImage = isImageExtension(file.extension ?? '');

    return Stack(
      clipBehavior: Clip.none,
      children: [
        Container(
          width: 70,
          height: 70,
          decoration: BoxDecoration(
            color: Colors.grey[200],
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: Colors.grey[300]!),
          ),
          clipBehavior: Clip.antiAlias,
          child: isImage && file.path != null
              ? Image.file(
                  File(file.path!),
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => _buildFileIcon(file),
                )
              : _buildFileIcon(file),
        ),
        Positioned(
          top: -6,
          right: -6,
          child: GestureDetector(
            onTap: () => onRemove(index),
            child: Container(
              width: 20,
              height: 20,
              decoration: const BoxDecoration(
                color: Colors.red,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.close,
                size: 14,
                color: Colors.white,
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildFileIcon(PlatformFile file) {
    final mime = mimeFromExtension(file.extension ?? '');
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        FileTypeIcon(mimeType: mime, size: 28),
        const SizedBox(height: 4),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4),
          child: Text(
            file.name,
            style: const TextStyle(fontSize: 9),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.center,
          ),
        ),
      ],
    );
  }
}
