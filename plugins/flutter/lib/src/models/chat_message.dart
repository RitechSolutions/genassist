/// Chat message models ported from React types/index.ts.

enum Speaker { customer, agent, special }

extension SpeakerExtension on Speaker {
  String toJson() => name;

  static Speaker fromJson(String value) {
    switch (value) {
      case 'customer':
        return Speaker.customer;
      case 'agent':
        return Speaker.agent;
      case 'special':
        return Speaker.special;
      default:
        return Speaker.customer;
    }
  }
}

class MessageFeedback {
  final String feedback; // "good" or "bad"
  final String? feedbackTimestamp;
  final String? feedbackUserId;
  final String? feedbackMessage;

  const MessageFeedback({
    required this.feedback,
    this.feedbackTimestamp,
    this.feedbackUserId,
    this.feedbackMessage,
  });

  factory MessageFeedback.fromJson(Map<String, dynamic> json) {
    return MessageFeedback(
      feedback: json['feedback'] as String,
      feedbackTimestamp: json['feedbackTimestamp'] as String?,
      feedbackUserId: json['feedbackUserId'] as String?,
      feedbackMessage: json['feedbackMessage'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'feedback': feedback,
      if (feedbackTimestamp != null) 'feedbackTimestamp': feedbackTimestamp,
      if (feedbackUserId != null) 'feedbackUserId': feedbackUserId,
      if (feedbackMessage != null) 'feedbackMessage': feedbackMessage,
    };
  }
}

class Attachment {
  final String name;
  final String type;
  final int size;
  final String url;
  final String? fileId;

  const Attachment({
    required this.name,
    required this.type,
    required this.size,
    required this.url,
    this.fileId,
  });

  factory Attachment.fromJson(Map<String, dynamic> json) {
    return Attachment(
      name: json['name'] as String,
      type: json['type'] as String,
      size: (json['size'] as num).toInt(),
      url: json['url'] as String,
      fileId: json['fileId'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'name': name,
      'type': type,
      'size': size,
      'url': url,
      if (fileId != null) 'fileId': fileId,
    };
  }
}

class ChatMessage {
  final double createTime;
  final double startTime;
  final double endTime;
  final Speaker speaker;
  final String text;
  final List<Attachment>? attachments;
  final String? messageId;
  final List<MessageFeedback>? feedback;
  final String? type;
  final String? linkUrl;
  final String? linkLabel;

  const ChatMessage({
    required this.createTime,
    required this.startTime,
    required this.endTime,
    required this.speaker,
    required this.text,
    this.attachments,
    this.messageId,
    this.feedback,
    this.type,
    this.linkUrl,
    this.linkLabel,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      createTime: (json['createTime'] as num).toDouble(),
      startTime: (json['startTime'] as num).toDouble(),
      endTime: (json['endTime'] as num).toDouble(),
      speaker: SpeakerExtension.fromJson(json['speaker'] as String),
      text: json['text'] as String,
      attachments: json['attachments'] != null
          ? (json['attachments'] as List<dynamic>)
              .map((e) => Attachment.fromJson(e as Map<String, dynamic>))
              .toList()
          : null,
      messageId: json['messageId'] as String?,
      feedback: json['feedback'] != null
          ? (json['feedback'] as List<dynamic>)
              .map((e) => MessageFeedback.fromJson(e as Map<String, dynamic>))
              .toList()
          : null,
      type: json['type'] as String?,
      linkUrl: json['linkUrl'] as String?,
      linkLabel: json['linkLabel'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'createTime': createTime,
      'startTime': startTime,
      'endTime': endTime,
      'speaker': speaker.toJson(),
      'text': text,
      if (attachments != null)
        'attachments': attachments!.map((e) => e.toJson()).toList(),
      if (messageId != null) 'messageId': messageId,
      if (feedback != null)
        'feedback': feedback!.map((e) => e.toJson()).toList(),
      if (type != null) 'type': type,
      if (linkUrl != null) 'linkUrl': linkUrl,
      if (linkLabel != null) 'linkLabel': linkLabel,
    };
  }

  ChatMessage copyWith({
    double? createTime,
    double? startTime,
    double? endTime,
    Speaker? speaker,
    String? text,
    List<Attachment>? attachments,
    String? messageId,
    List<MessageFeedback>? feedback,
    String? type,
    String? linkUrl,
    String? linkLabel,
  }) {
    return ChatMessage(
      createTime: createTime ?? this.createTime,
      startTime: startTime ?? this.startTime,
      endTime: endTime ?? this.endTime,
      speaker: speaker ?? this.speaker,
      text: text ?? this.text,
      attachments: attachments ?? this.attachments,
      messageId: messageId ?? this.messageId,
      feedback: feedback ?? this.feedback,
      type: type ?? this.type,
      linkUrl: linkUrl ?? this.linkUrl,
      linkLabel: linkLabel ?? this.linkLabel,
    );
  }
}
