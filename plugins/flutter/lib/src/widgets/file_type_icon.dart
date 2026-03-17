import 'package:flutter/material.dart';

class FileTypeIcon extends StatelessWidget {
  final String mimeType;
  final double size;
  final Color? color;

  const FileTypeIcon({
    super.key,
    required this.mimeType,
    this.size = 24,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final iconData = _iconForMimeType(mimeType);
    final iconColor = color ?? _colorForMimeType(mimeType);

    return Icon(
      iconData,
      size: size,
      color: iconColor,
    );
  }

  IconData _iconForMimeType(String mime) {
    final lower = mime.toLowerCase();

    if (lower == 'application/pdf') {
      return Icons.picture_as_pdf;
    }
    if (lower == 'application/msword' ||
        lower.contains('wordprocessingml') ||
        lower.contains('word')) {
      return Icons.description;
    }
    if (lower.contains('spreadsheet') ||
        lower.contains('excel') ||
        lower == 'text/csv') {
      return Icons.table_chart;
    }
    if (lower.contains('presentation') || lower.contains('powerpoint')) {
      return Icons.slideshow;
    }
    if (lower.startsWith('image/')) {
      return Icons.image;
    }
    if (lower.startsWith('video/')) {
      return Icons.videocam;
    }
    if (lower.startsWith('audio/')) {
      return Icons.audiotrack;
    }
    if (lower.startsWith('text/')) {
      return Icons.article;
    }
    if (lower.contains('zip') ||
        lower.contains('rar') ||
        lower.contains('tar') ||
        lower.contains('gzip')) {
      return Icons.folder_zip;
    }

    return Icons.insert_drive_file;
  }

  Color _colorForMimeType(String mime) {
    final lower = mime.toLowerCase();

    if (lower == 'application/pdf') {
      return const Color(0xFFE53935);
    }
    if (lower.contains('word') || lower.contains('wordprocessingml')) {
      return const Color(0xFF1565C0);
    }
    if (lower.contains('spreadsheet') || lower.contains('excel')) {
      return const Color(0xFF2E7D32);
    }
    if (lower.contains('presentation') || lower.contains('powerpoint')) {
      return const Color(0xFFE65100);
    }
    if (lower.startsWith('image/')) {
      return const Color(0xFF7B1FA2);
    }
    if (lower.startsWith('video/')) {
      return const Color(0xFFD32F2F);
    }
    if (lower.startsWith('audio/')) {
      return const Color(0xFF1976D2);
    }

    return const Color(0xFF757575);
  }
}
