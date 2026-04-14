/// Configuration models for the GenAssist chat widget.

import 'package:flutter/material.dart';

enum ChatMode { embedded, floating, fullscreen }

enum FloatingPosition { bottomRight, bottomLeft, topRight, topLeft }

class FloatingConfig {
  final FloatingPosition position;
  final Offset offset;
  final Widget? toggleButtonIcon;
  final Widget? closeButtonIcon;

  const FloatingConfig({
    this.position = FloatingPosition.bottomRight,
    this.offset = const Offset(16, 16),
    this.toggleButtonIcon,
    this.closeButtonIcon,
  });
}

class GenAgentChatTheme {
  static const Color defaultPrimaryColor = Color(0xFF6366F1);

  final Color? primaryColor;
  final Color? secondaryColor;
  final String? fontFamily;
  final double? fontSize;
  final Color? backgroundColor;
  final Color? textColor;

  const GenAgentChatTheme({
    this.primaryColor,
    this.secondaryColor,
    this.fontFamily,
    this.fontSize,
    this.backgroundColor,
    this.textColor,
  });

  /// Resolve primary color with fallback to default.
  Color get resolvedPrimaryColor => primaryColor ?? defaultPrimaryColor;
}

/// Convert a file extension string to its MIME type.
String mimeFromExtension(String ext) {
  switch (ext.toLowerCase()) {
    case 'png':
      return 'image/png';
    case 'jpg':
    case 'jpeg':
      return 'image/jpeg';
    case 'gif':
      return 'image/gif';
    case 'webp':
      return 'image/webp';
    case 'bmp':
      return 'image/bmp';
    case 'pdf':
      return 'application/pdf';
    case 'doc':
      return 'application/msword';
    case 'docx':
      return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    default:
      return 'application/octet-stream';
  }
}

/// Check if a file extension is an image type.
bool isImageExtension(String ext) {
  return ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'].contains(ext.toLowerCase());
}

enum AllowedExtension {
  imageAll,
  imagePng,
  imageJpeg,
  imageJpg,
  imageGif,
  applicationPdf,
  applicationMsword,
  applicationDocx,
}

extension AllowedExtensionMimeType on AllowedExtension {
  /// Returns the MIME type string for this extension.
  String get mimeType {
    switch (this) {
      case AllowedExtension.imageAll:
        return 'image/*';
      case AllowedExtension.imagePng:
        return 'image/png';
      case AllowedExtension.imageJpeg:
        return 'image/jpeg';
      case AllowedExtension.imageJpg:
        return 'image/jpg';
      case AllowedExtension.imageGif:
        return 'image/gif';
      case AllowedExtension.applicationPdf:
        return 'application/pdf';
      case AllowedExtension.applicationMsword:
        return 'application/msword';
      case AllowedExtension.applicationDocx:
        return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    }
  }
}
