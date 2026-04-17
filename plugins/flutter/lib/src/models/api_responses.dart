/// API response models for the GenAssist chat service.

import 'chat_message.dart';

class StartConversationResponse {
  final String message;
  final String conversationId;
  final String? agentWelcomeMessage;
  final List<String>? agentPossibleQueries;
  final String? agentWelcomeTitle;
  final String? agentWelcomeImageUrl;
  final String? agentId;
  final List<String>? agentAvailableLanguages;
  final List<String>? agentThinkingPhrases;
  final double? agentThinkingPhraseDelay; // seconds
  final Map<String, dynamic>? agentChatInputMetadata;
  final String? agentInputDisclaimerHtml;
  final double? createTime;
  final String? guestToken;

  const StartConversationResponse({
    required this.message,
    required this.conversationId,
    this.agentWelcomeMessage,
    this.agentPossibleQueries,
    this.agentWelcomeTitle,
    this.agentWelcomeImageUrl,
    this.agentId,
    this.agentAvailableLanguages,
    this.agentThinkingPhrases,
    this.agentThinkingPhraseDelay,
    this.agentChatInputMetadata,
    this.agentInputDisclaimerHtml,
    this.createTime,
    this.guestToken,
  });

  factory StartConversationResponse.fromJson(Map<String, dynamic> json) {
    return StartConversationResponse(
      message: json['message'] as String,
      conversationId: json['conversationId'] as String,
      agentWelcomeMessage: json['agentWelcomeMessage'] as String?,
      agentPossibleQueries: json['agentPossibleQueries'] != null
          ? (json['agentPossibleQueries'] as List<dynamic>)
              .map((e) => e as String)
              .toList()
          : null,
      agentWelcomeTitle: json['agentWelcomeTitle'] as String?,
      agentWelcomeImageUrl: json['agentWelcomeImageUrl'] as String?,
      agentId: json['agentId'] as String?,
      agentAvailableLanguages: json['agentAvailableLanguages'] != null
          ? (json['agentAvailableLanguages'] as List<dynamic>)
              .map((e) => e as String)
              .toList()
          : null,
      agentThinkingPhrases: json['agentThinkingPhrases'] != null
          ? (json['agentThinkingPhrases'] as List<dynamic>)
              .map((e) => e as String)
              .toList()
          : null,
      agentThinkingPhraseDelay:
          (json['agentThinkingPhraseDelay'] as num?)?.toDouble(),
      agentChatInputMetadata:
          json['agentChatInputMetadata'] as Map<String, dynamic>?,
      agentInputDisclaimerHtml: json['agentInputDisclaimerHtml'] as String?,
      createTime: (json['createTime'] as num?)?.toDouble(),
      guestToken: json['guestToken'] as String?,
    );
  }
}

class AgentInfoResponse {
  final String? agentId;
  final List<String>? agentAvailableLanguages;

  const AgentInfoResponse({
    this.agentId,
    this.agentAvailableLanguages,
  });

  factory AgentInfoResponse.fromJson(Map<String, dynamic> json) {
    return AgentInfoResponse(
      agentId: json['agentId'] as String?,
      agentAvailableLanguages: json['agentAvailableLanguages'] != null
          ? (json['agentAvailableLanguages'] as List<dynamic>)
              .map((e) => e as String)
              .toList()
          : null,
    );
  }
}

class AgentWelcomeData {
  String? title;
  String? message;
  String? imageUrl;
  List<String> possibleQueries;
  String? inputDisclaimerHtml;

  AgentWelcomeData({
    this.title,
    this.message,
    this.imageUrl,
    List<String>? possibleQueries,
    this.inputDisclaimerHtml,
  }) : possibleQueries = possibleQueries ?? [];

  factory AgentWelcomeData.fromJson(Map<String, dynamic> json) {
    return AgentWelcomeData(
      title: json['title'] as String?,
      message: json['message'] as String?,
      imageUrl: json['imageUrl'] as String?,
      possibleQueries: json['possibleQueries'] != null
          ? (json['possibleQueries'] as List<dynamic>)
              .map((e) => e as String)
              .toList()
          : [],
      inputDisclaimerHtml: json['inputDisclaimerHtml'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      if (title != null) 'title': title,
      if (message != null) 'message': message,
      if (imageUrl != null) 'imageUrl': imageUrl,
      'possibleQueries': possibleQueries,
      if (inputDisclaimerHtml != null)
        'inputDisclaimerHtml': inputDisclaimerHtml,
    };
  }
}

class AgentThinkingConfig {
  List<String> phrases;
  int delayMs; // milliseconds

  AgentThinkingConfig({
    List<String>? phrases,
    this.delayMs = 3000,
  }) : phrases = phrases ?? [];
}

class FileUploadResponse {
  final String filename;
  final String originalFilename;
  final String storagePath;
  final String filePath;
  final String fileUrl;
  final String? fileId;

  const FileUploadResponse({
    required this.filename,
    required this.originalFilename,
    required this.storagePath,
    required this.filePath,
    required this.fileUrl,
    this.fileId,
  });

  factory FileUploadResponse.fromJson(Map<String, dynamic> json) {
    return FileUploadResponse(
      filename: json['filename'] as String,
      originalFilename: json['originalFilename'] as String,
      storagePath: json['storagePath'] as String,
      filePath: json['filePath'] as String,
      fileUrl: json['fileUrl'] as String,
      fileId: json['fileId'] as String?,
    );
  }
}

class InProgressPollMessage {
  final String id;
  final dynamic createTime; // can be string or number
  final double startTime;
  final double endTime;
  final String speaker;
  final String text;
  final String? type;
  final int? sequenceNumber;
  final List<MessageFeedback>? feedback;

  const InProgressPollMessage({
    required this.id,
    required this.createTime,
    required this.startTime,
    required this.endTime,
    required this.speaker,
    required this.text,
    this.type,
    this.sequenceNumber,
    this.feedback,
  });

  factory InProgressPollMessage.fromJson(Map<String, dynamic> json) {
    return InProgressPollMessage(
      id: json['id'] as String,
      createTime: json['createTime'], // keep as dynamic
      startTime: (json['startTime'] as num).toDouble(),
      endTime: (json['endTime'] as num).toDouble(),
      speaker: json['speaker'] as String,
      text: json['text'] as String,
      type: json['type'] as String?,
      sequenceNumber: (json['sequenceNumber'] as num?)?.toInt(),
      feedback: json['feedback'] != null
          ? (json['feedback'] as List<dynamic>)
              .map((e) => MessageFeedback.fromJson(e as Map<String, dynamic>))
              .toList()
          : null,
    );
  }
}

class InProgressPollResponse {
  final String status;
  final List<InProgressPollMessage> messages;

  const InProgressPollResponse({
    required this.status,
    required this.messages,
  });

  factory InProgressPollResponse.fromJson(Map<String, dynamic> json) {
    return InProgressPollResponse(
      status: json['status'] as String,
      messages: (json['messages'] as List<dynamic>)
          .map(
              (e) => InProgressPollMessage.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
