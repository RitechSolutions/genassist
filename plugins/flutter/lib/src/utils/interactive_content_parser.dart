import 'dart:convert';
import '../models/interactive_content.dart';

final _jsonBlockRegex = RegExp(r'```json\s*([\s\S]*?)\s*```');
final _optionsRegex = RegExp(r'\*\*\*(.*?)\*\*\*');

bool _isDynamicChatItem(dynamic value) {
  return value is Map<String, dynamic> &&
      value['id'] is String &&
      value['name'] is String;
}

bool _isScheduleItem(dynamic value) {
  return value is Map<String, dynamic> &&
      value['id'] is String &&
      value['restaurants'] is List;
}

bool _isFileItem(dynamic value) {
  return value is Map<String, dynamic> &&
      value['url'] is String &&
      value['type'] is String &&
      value['name'] is String &&
      value['id'] is String;
}

ChatContentBlock? _parseJsonBlock(String jsonString) {
  try {
    final parsed = json.decode(jsonString);
    if (_isScheduleItem(parsed)) {
      return ScheduleBlock(
        schedule: ScheduleItem.fromJson(parsed as Map<String, dynamic>),
      );
    }
    if (parsed is List && parsed.every(_isDynamicChatItem)) {
      return ItemsBlock(
        items: parsed
            .map((e) => DynamicChatItem.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
    }
  } catch (_) {
    // ignore malformed JSON blocks
  }
  return null;
}

/// A record of a regex match with its position and type.
class _MatchRecord {
  final int start;
  final int end;
  final String type; // "json" or "options"
  final String content;

  const _MatchRecord({
    required this.start,
    required this.end,
    required this.type,
    required this.content,
  });
}

/// Parse interactive content blocks from a message text.
///
/// Recognizes JSON code blocks (```json ... ```), option markers (***...***),
/// and file-type messages.
List<ChatContentBlock> parseInteractiveContentBlocks(String text,
    {String? messageType}) {
  // Handle file items
  if (messageType == 'file') {
    try {
      final cleanJson = text.replaceAll(r'\', '');
      final parsed = json.decode(cleanJson);
      if (_isFileItem(parsed)) {
        return [FileBlock(data: FileItem.fromJson(parsed as Map<String, dynamic>))];
      }
    } catch (_) {
      // fall through to normal parsing
    }
  }

  // Try parsing the whole text as a file item
  try {
    final parsed = json.decode(text);
    if (_isFileItem(parsed)) {
      return [FileBlock(data: FileItem.fromJson(parsed as Map<String, dynamic>))];
    }
  } catch (_) {
    // not a file item, continue
  }

  final matches = <_MatchRecord>[];

  // Find JSON blocks
  for (final jsonMatch in _jsonBlockRegex.allMatches(text)) {
    final content = jsonMatch.group(1);
    if (content == null || content.isEmpty) continue;
    matches.add(_MatchRecord(
      start: jsonMatch.start,
      end: jsonMatch.end,
      type: 'json',
      content: content,
    ));
  }

  // Find option blocks
  for (final optionsMatch in _optionsRegex.allMatches(text)) {
    final content = optionsMatch.group(1);
    if (content == null || content.isEmpty) continue;
    matches.add(_MatchRecord(
      start: optionsMatch.start,
      end: optionsMatch.end,
      type: 'options',
      content: content,
    ));
  }

  if (matches.isEmpty) {
    final trimmed = text.trim();
    return trimmed.isNotEmpty ? [TextBlock(text: trimmed)] : [];
  }

  matches.sort((a, b) => a.start.compareTo(b.start));

  final blocks = <ChatContentBlock>[];
  var lastIndex = 0;

  for (final match in matches) {
    if (lastIndex < match.start) {
      final before = text.substring(lastIndex, match.start).trim();
      if (before.isNotEmpty) {
        blocks.add(TextBlock(text: before));
      }
    }

    if (match.type == 'json') {
      final block = _parseJsonBlock(match.content);
      if (block != null) {
        blocks.add(block);
      }
    } else {
      final options = match.content
          .split(';')
          .map((opt) => opt.trim())
          .where((opt) => opt.isNotEmpty)
          .toList();
      if (options.isNotEmpty) {
        blocks.add(OptionsBlock(options: options));
      }
    }

    lastIndex = match.end;
  }

  if (lastIndex < text.length) {
    final after = text.substring(lastIndex).trim();
    if (after.isNotEmpty) {
      blocks.add(TextBlock(text: after));
    }
  }

  return blocks;
}

/// Generate message content string from a list of content blocks.
String generateMessageContent(List<ChatContentBlock> blocks) {
  final buffer = StringBuffer();

  for (final block in blocks) {
    switch (block) {
      case TextBlock(:final text):
        buffer.write(text);
      case ItemsBlock(:final items):
        buffer.write('```json\n${json.encode(items.map((e) => e.toJson()).toList())}\n```');
      case ScheduleBlock(:final schedule):
        buffer.write('```json\n${json.encode(schedule.toJson())}\n```');
      case OptionsBlock(:final options):
        buffer.write('***${options.join("; ")}***');
      case FileBlock():
        break;
    }
  }

  return buffer.toString();
}
