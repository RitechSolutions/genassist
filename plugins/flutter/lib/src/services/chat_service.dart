/// Main HTTP API client for GenAssist chat.
/// Ported from React chatService.ts.

import 'dart:convert';
import 'dart:io' show File;

import 'package:http/http.dart' as http;

import '../models/chat_message.dart';
import '../models/api_responses.dart';
import '../utils/accept_language.dart';
import 'storage_service.dart';

/// Event name constant (useful for inter-service communication).
const String genassistAgentMetadataUpdated = 'genassist_agent_metadata_updated';

class ChatService {
  // ── Configuration ──────────────────────────────────────────────────
  final String baseUrl;
  final String? websocketUrl;
  final String apiKey;
  Map<String, dynamic>? metadata;
  String? tenant;
  String? language;
  final bool useWs;
  final bool usePoll;

  // ── Internal state ─────────────────────────────────────────────────
  String? _conversationId;
  double? _conversationCreateTime;
  String? _guestToken;
  bool _isFinalized = false;
  List<String> _possibleQueries = [];
  AgentWelcomeData _welcomeData = AgentWelcomeData();
  AgentThinkingConfig _thinkingConfig = AgentThinkingConfig();
  Map<String, dynamic> _chatInputMetadata = {};
  String? _agentId;
  List<String>? _availableLanguages;
  int _wsVersion = 1;

  String? serverUnavailableMessage;
  String? serverUnavailableContactUrl;
  String? serverUnavailableContactLabel;

  // ── Callbacks ──────────────────────────────────────────────────────
  void Function(ChatMessage message)? messageHandler;
  void Function()? takeoverHandler;
  void Function()? finalizedHandler;
  void Function(String state)? connectionStateHandler;
  void Function(AgentWelcomeData data)? welcomeDataHandler;

  // ── Services ───────────────────────────────────────────────────────
  final StorageService _storage;
  final http.Client _httpClient;

  // ── Constructor ────────────────────────────────────────────────────
  ChatService({
    required String baseUrl,
    this.websocketUrl,
    required this.apiKey,
    this.metadata,
    this.tenant,
    this.language,
    this.useWs = true,
    this.usePoll = false,
    http.Client? httpClient,
  })  : baseUrl = baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl,
        _storage = StorageService(apiKey: apiKey),
        _httpClient = httpClient ?? http.Client() {
    if (websocketUrl != null) {
      _wsVersion = 2;
    }
  }

  // ── Getters ────────────────────────────────────────────────────────
  String? get conversationId => _conversationId;
  double? get conversationCreateTime => _conversationCreateTime;
  String? get guestToken => _guestToken;
  bool get isFinalized => _isFinalized;
  List<String> get possibleQueries => List.unmodifiable(_possibleQueries);
  AgentWelcomeData get welcomeData => _welcomeData;
  AgentThinkingConfig get thinkingConfig => _thinkingConfig;
  Map<String, dynamic> get chatInputMetadata => Map.unmodifiable(_chatInputMetadata);
  String? get agentId => _agentId;
  List<String>? get availableLanguages =>
      _availableLanguages != null ? List.unmodifiable(_availableLanguages!) : null;
  bool get hasActiveConversation => _conversationId != null;

  // ── Language ───────────────────────────────────────────────────────


  // ── Headers ────────────────────────────────────────────────────────

  Map<String, String> _getHeaders({String contentType = 'application/json'}) {
    final headers = <String, String>{
      'x-api-key': apiKey,
      'Content-Type': contentType,
    };
    if (tenant != null) {
      headers['x-tenant-id'] = tenant!;
    }
    if (_guestToken != null) {
      headers['Authorization'] = 'Bearer $_guestToken';
    }
    if (language != null && language!.isNotEmpty) {
      final acceptLanguage = formatAcceptLanguage(language!);
      if (acceptLanguage.isNotEmpty) {
        headers['Accept-Language'] = acceptLanguage;
      }
    }
    return headers;
  }

  // ── Persistence helpers ────────────────────────────────────────────

  Future<void> loadSavedConversation() async {
    final saved = await _storage.loadSavedConversation();
    if (saved == null) return;

    _conversationId = saved['conversationId'] as String?;
    _conversationCreateTime = (saved['createTime'] as num?)?.toDouble();
    _isFinalized = saved['isFinalized'] as bool? ?? false;
    _guestToken = saved['guestToken'] as String?;

    final rawQueries = saved['possibleQueries'];
    _possibleQueries = rawQueries is List
        ? rawQueries.whereType<String>().toList()
        : [];

    final welcomeJson = saved['welcomeData'];
    _welcomeData = welcomeJson is Map<String, dynamic>
        ? AgentWelcomeData.fromJson(welcomeJson)
        : AgentWelcomeData();

    if (_welcomeData.possibleQueries.isEmpty) {
      _welcomeData.possibleQueries = _possibleQueries;
    }

    final thinkingJson = saved['thinkingConfig'];
    if (thinkingJson is Map<String, dynamic>) {
      final phrases = thinkingJson['phrases'];
      final delayMs = thinkingJson['delayMs'];
      _thinkingConfig = AgentThinkingConfig(
        phrases: phrases is List ? phrases.whereType<String>().toList() : [],
        delayMs: delayMs is num ? delayMs.toInt() : 1000,
      );
    }

    _agentId = saved['agentId'] as String?;
    final rawLangs = saved['availableLanguages'];
    if (rawLangs is List) {
      _availableLanguages = rawLangs.whereType<String>().toList();
    }

    if (_welcomeData.imageUrl == null && _agentId != null) {
      await fetchWelcomeImage(_agentId!);
    }
    welcomeDataHandler?.call(_welcomeData);
  }

  Future<void> _saveConversation() async {
    if (_conversationId == null || _conversationCreateTime == null) return;
    await _storage.saveConversation(
      conversationId: _conversationId!,
      createTime: _conversationCreateTime!,
      isFinalized: _isFinalized,
      possibleQueries: _possibleQueries,
      welcomeData: _welcomeData,
      thinkingConfig: _thinkingConfig,
      agentId: _agentId,
      guestToken: _guestToken,
      availableLanguages: _availableLanguages,
    );
  }

  // ── Token expiry check ─────────────────────────────────────────────

  bool _isTokenExpiredError(http.Response response) {
    if (response.statusCode != 401) return false;
    try {
      final body = jsonDecode(response.body);
      if (body is Map<String, dynamic>) {
        final err = body['error'] ?? body['message'] ?? '';
        if (err.toString().contains('Token has expired')) return true;
      }
      if (response.body.contains('Token has expired')) return true;
    } catch (_) {}
    return false;
  }

  // ── Conversation lifecycle ─────────────────────────────────────────

  /// Handle conversation finalized: emit special message, call handler, persist.
  void handleConversationFinalized() {
    if (messageHandler != null) {
      final now = DateTime.now().millisecondsSinceEpoch / 1000.0;
      final finalizedMessage = ChatMessage(
        createTime: now,
        startTime: _conversationCreateTime != null ? now - _conversationCreateTime! : 0,
        endTime: _conversationCreateTime != null ? now - _conversationCreateTime! + 0.01 : 0.01,
        speaker: Speaker.special,
        text: 'Conversation Finalized',
        type: 'finalized',
      );
      messageHandler!(finalizedMessage);
    }
    finalizedHandler?.call();
    _isFinalized = true;
    _saveConversation();
  }

  /// Internal handler for takeover events.
  void handleTakeover({double? now}) {
    final t = now ?? DateTime.now().millisecondsSinceEpoch / 1000.0;
    if (messageHandler != null) {
      final takeoverMessage = ChatMessage(
        createTime: t,
        startTime: _conversationCreateTime != null ? t - _conversationCreateTime! : 0,
        endTime: _conversationCreateTime != null ? t - _conversationCreateTime! + 0.01 : 0.01,
        speaker: Speaker.special,
        text: 'Supervisor took over',
        type: 'takeover',
      );
      messageHandler!(takeoverMessage);
    }
    takeoverHandler?.call();
  }

  /// Reset the current conversation by clearing the ID and state.
  Future<void> resetChatConversation() async {
    _conversationId = null;
    _conversationCreateTime = null;
    _guestToken = null;
    _isFinalized = false;
    _possibleQueries = [];
    _welcomeData = AgentWelcomeData();
    _thinkingConfig = AgentThinkingConfig();
    _chatInputMetadata = {};
    _agentId = null;
    await _storage.clearConversation();
  }

  // ── API methods ────────────────────────────────────────────────────

  /// Fetch agent metadata without starting a conversation.
  Future<AgentInfoResponse?> fetchAgentInfo() async {
    try {
      final uri = Uri.parse('$baseUrl/api/conversations/in-progress/agent-info');
      final response = await _httpClient.get(uri, headers: _getHeaders());
      if (response.statusCode != 200) return null;

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final agentIdVal = data['agent_id'] as String?;
      final rawLangs = data['agent_available_languages'];
      List<String>? parsedLangs;
      if (rawLangs is List) {
        parsedLangs = rawLangs
            .whereType<String>()
            .where((l) => l.trim().isNotEmpty)
            .map((l) => l.toLowerCase())
            .toList();
      }

      if (agentIdVal != null) _agentId = agentIdVal;
      if (parsedLangs != null) _availableLanguages = parsedLangs;

      return AgentInfoResponse(
        agentId: agentIdVal,
        agentAvailableLanguages: parsedLangs,
      );
    } catch (_) {
      return null;
    }
  }

  /// Fetch the agent welcome image and store the raw bytes URL.
  Future<void> fetchWelcomeImage(String agentIdVal) async {
    try {
      final uri = Uri.parse(
          '$baseUrl/api/genagent/agents/configs/$agentIdVal/welcome-image');
      final response = await _httpClient.get(uri, headers: _getHeaders());
      if (response.statusCode == 200 && response.bodyBytes.isNotEmpty) {
        // In Flutter we can't create blob URLs. Store as a data URI instead.
        final mimeType = response.headers['content-type'] ?? 'image/png';
        final base64Data = base64Encode(response.bodyBytes);
        final dataUri = 'data:$mimeType;base64,$base64Data';
        _welcomeData.imageUrl = dataUri;
        welcomeDataHandler?.call(_welcomeData);
      }
    } catch (e) {
      // If token expired, reset. Otherwise ignore.
      if (e is http.ClientException) {
        // can't check status here, ignore
      }
    }
  }

  /// Start a new conversation.
  Future<String> startConversation({String? reCaptchaToken}) async {
    final requestBody = <String, dynamic>{
      'messages': <dynamic>[],
      'recorded_at': DateTime.now().toUtc().toIso8601String(),
      'data_source_id': '00000000-0000-0000-0000-000000000000',
    };

    if (reCaptchaToken != null) {
      requestBody['recaptcha_token'] = reCaptchaToken;
    }
    if (metadata != null && metadata!.isNotEmpty) {
      requestBody['metadata'] = metadata;
    }

    final uri = Uri.parse('$baseUrl/api/conversations/in-progress/start');
    final response = await _httpClient.post(
      uri,
      headers: _getHeaders(),
      body: jsonEncode(requestBody),
    );

    if (_isTokenExpiredError(response)) {
      await resetChatConversation();
      throw Exception('Token has expired');
    }

    if (response.statusCode != 200 && response.statusCode != 201) {
      throw Exception('Failed to start conversation: ${response.statusCode} ${response.body}');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    _conversationId = data['conversation_id'] as String;
    _conversationCreateTime = data['create_time'] != null
        ? (data['create_time'] as num).toDouble() / 1000.0
        : DateTime.now().millisecondsSinceEpoch / 1000.0;
    _guestToken = data['guest_token'] as String?;
    _isFinalized = false;

    // Possible queries
    final rawQueries = data['agent_possible_queries'];
    if (rawQueries is List && rawQueries.isNotEmpty) {
      _possibleQueries = rawQueries
          .whereType<String>()
          .where((q) => q.trim().isNotEmpty)
          .toList();
    }

    // Agent info
    _agentId = data['agent_id'] as String?;
    final rawLangs = data['agent_available_languages'];
    if (rawLangs is List) {
      _availableLanguages = rawLangs
          .whereType<String>()
          .where((l) => l.trim().isNotEmpty)
          .map((l) => l.toLowerCase())
          .toList();
    }

    // Chat input metadata
    final rawMeta = data['agent_chat_input_metadata'];
    if (rawMeta is Map<String, dynamic>) {
      _chatInputMetadata = Map<String, dynamic>.from(rawMeta);
    } else {
      _chatInputMetadata = {};
    }

    // Welcome data
    final welcomeTitle = data['agent_welcome_title'] as String?;
    final welcomeImageUrl = data['agent_welcome_image_url'] as String?;
    final thinkingPhrases = data['agent_thinking_phrases'];
    final thinkingDelaySec = data['agent_thinking_phrase_delay'];
    final inputDisclaimerHtml = data['agent_input_disclaimer_html'] as String?;

    _welcomeData = AgentWelcomeData(
      title: welcomeTitle,
      message: null,
      imageUrl: welcomeImageUrl,
      possibleQueries: _possibleQueries,
      inputDisclaimerHtml: inputDisclaimerHtml,
    );

    if (thinkingPhrases is List && thinkingPhrases.isNotEmpty) {
      _thinkingConfig.phrases = thinkingPhrases.whereType<String>().toList();
    }
    if (thinkingDelaySec is num && thinkingDelaySec >= 0) {
      _thinkingConfig.delayMs = (thinkingDelaySec * 1000).round().clamp(250, 999999);
    }

    if (_welcomeData.imageUrl == null && _agentId != null) {
      await fetchWelcomeImage(_agentId!);
    }

    // Keep welcome message in welcome-card data only (don't inject as a
    // transcript bubble on conversation start).
    final agentWelcomeMessage = data['agent_welcome_message'] as String?;
    if (agentWelcomeMessage != null) {
      _welcomeData.message = agentWelcomeMessage;
    }

    welcomeDataHandler?.call(_welcomeData);
    await _saveConversation();
    return _conversationId!;
  }

  /// Send a user message to the current conversation.
  Future<void> sendMessage(
    String message, {
    List<Attachment>? attachments,
    Map<String, dynamic>? extraMetadata,
    String? reCaptchaToken,
  }) async {
    if (_conversationId == null || _conversationCreateTime == null) {
      throw Exception('Conversation not started');
    }

    final now = DateTime.now().millisecondsSinceEpoch / 1000.0;
    final chatMessage = ChatMessage(
      createTime: now,
      startTime: now - _conversationCreateTime!,
      endTime: now - _conversationCreateTime! + 0.01,
      speaker: Speaker.customer,
      text: message,
      attachments: attachments,
    );

    messageHandler?.call(chatMessage);

    final requestBody = <String, dynamic>{
      'messages': [
        {
          'create_time': chatMessage.createTime,
          'start_time': chatMessage.startTime,
          'end_time': chatMessage.endTime,
          'speaker': chatMessage.speaker.toJson(),
          'text': chatMessage.text,
          if (attachments != null && attachments.isNotEmpty)
            'attachments': attachments.map((a) => a.toJson()).toList(),
        }
      ],
      'recorded_at': DateTime.now().toUtc().toIso8601String(),
    };

    if (reCaptchaToken != null) {
      requestBody['recaptcha_token'] = reCaptchaToken;
    }

    final mergedMetadata = <String, dynamic>{
      ...?metadata,
      ...?extraMetadata,
    };
    if (mergedMetadata.isNotEmpty) {
      requestBody['metadata'] = mergedMetadata;
    }

    try {
      final uri = Uri.parse(
          '$baseUrl/api/conversations/in-progress/update/$_conversationId');
      final response = await _httpClient.patch(
        uri,
        headers: _getHeaders(),
        body: jsonEncode(requestBody),
      );

      if (_isTokenExpiredError(response)) {
        await resetChatConversation();
        throw Exception('Token has expired');
      }

      // Check for finalized / agent not found errors
      if (response.statusCode >= 400) {
        try {
          final errBody = jsonDecode(response.body) as Map<String, dynamic>;
          final errorKey = errBody['error_key'] as String?;
          if (errorKey == 'CONVERSATION_FINALIZED' || errorKey == 'AGENT_NOT_FOUND') {
            handleConversationFinalized();
            return;
          }
          if (errorKey == 'AGENT_INACTIVE') {
            _emitServerUnavailableMessage(now);
            return;
          }
        } catch (_) {}
        throw Exception('Send message failed: ${response.statusCode} ${response.body}');
      }

      // If not using WebSocket, extract response messages
      if (!useWs && messageHandler != null && !usePoll) {
        try {
          final responseData = jsonDecode(response.body) as Map<String, dynamic>;
          final messages = responseData['messages'];
          if (messages is List) {
            for (int i = messages.length - 1; i >= 0; i--) {
              final msgData = messages[i] as Map<String, dynamic>;
              if (msgData['speaker'] == 'agent' &&
                  msgData['text'] != null &&
                  msgData['create_time'] != null &&
                  msgData['start_time'] != null &&
                  msgData['end_time'] != null) {
                final agentMsg = ChatMessage(
                  createTime: (msgData['create_time'] as num).toDouble(),
                  startTime: _conversationCreateTime != null
                      ? (msgData['start_time'] as num).toDouble() - _conversationCreateTime!
                      : (msgData['start_time'] as num).toDouble(),
                  endTime: _conversationCreateTime != null
                      ? (msgData['end_time'] as num).toDouble() - _conversationCreateTime!
                      : (msgData['end_time'] as num).toDouble(),
                  speaker: Speaker.agent,
                  text: msgData['text'] as String,
                  messageId: (msgData['message_id'] ?? msgData['id']) as String?,
                  type: msgData['type'] as String?,
                );
                messageHandler!(agentMsg);
                break;
              }
            }
          }
        } catch (_) {
          // Failed to parse update response
        }
      }
    } catch (e) {
      // Check for network/server errors at the transport level
      if (e is http.ClientException || e is FormatException) {
        _emitServerUnavailableMessage(now);
        return;
      }
      rethrow;
    }
  }

  void _emitServerUnavailableMessage(double now) {
    if (messageHandler == null) return;
    final errorMessage = ChatMessage(
      createTime: now,
      startTime: _conversationCreateTime != null ? now - _conversationCreateTime! : 0,
      endTime: _conversationCreateTime != null ? now - _conversationCreateTime! + 0.01 : 0.01,
      speaker: Speaker.special,
      text: serverUnavailableMessage ??
          'The agent is currently offline, please check back later. Thank you!',
      linkUrl: serverUnavailableContactUrl,
      linkLabel: serverUnavailableContactLabel ?? 'Contact support',
    );
    messageHandler!(errorMessage);
  }

  /// Upload a file for the current conversation.
  Future<FileUploadResponse?> uploadFile(String chatId, File file) async {
    if (_conversationId == null) {
      throw Exception('Conversation not started');
    }

    final uri =
        Uri.parse('$baseUrl/api/genagent/knowledge/upload-chat-file');
    final request = http.MultipartRequest('POST', uri);

    // Add headers (excluding Content-Type which is set by MultipartRequest)
    final headers = _getHeaders();
    headers.remove('Content-Type');
    request.headers.addAll(headers);

    request.fields['chat_id'] = chatId;
    request.files.add(await http.MultipartFile.fromPath('file', file.path));

    final streamedResponse = await _httpClient.send(request);
    final response = await http.Response.fromStream(streamedResponse);

    if (_isTokenExpiredError(response)) {
      await resetChatConversation();
      throw Exception('Token has expired');
    }

    if (response.statusCode != 200 && response.statusCode != 201) {
      throw Exception('File upload failed: ${response.statusCode} ${response.body}');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return FileUploadResponse(
      filename: data['filename'] as String,
      originalFilename: data['original_filename'] as String,
      storagePath: data['storage_path'] as String,
      filePath: data['file_path'] as String,
      fileUrl: data['file_url'] as String,
      fileId: data['file_id'] as String?,
    );
  }

  /// Add feedback to a specific agent message.
  Future<void> addFeedback(
    String messageId,
    String feedback, {
    String? feedbackMessage,
  }) async {
    if (messageId.isEmpty) {
      throw Exception('Message ID is required for feedback');
    }

    final uri = Uri.parse(
        '$baseUrl/api/conversations/message/add-feedback/$messageId');
    final payload = <String, dynamic>{
      'feedback': feedback,
      if (feedbackMessage != null) 'feedback_message': feedbackMessage,
    };

    final response = await _httpClient.patch(
      uri,
      headers: _getHeaders(),
      body: jsonEncode(payload),
    );

    if (_isTokenExpiredError(response)) {
      await resetChatConversation();
      throw Exception('Token has expired');
    }

    if (response.statusCode >= 400) {
      throw Exception('Feedback failed: ${response.statusCode} ${response.body}');
    }
  }

  // ── WebSocket message processing ───────────────────────────────────

  /// Process raw WebSocket message data. Called from WebSocketService.
  /// Handles message, takeover, and finalize events.
  void processWebSocketMessage(Map<String, dynamic> data) {
    if (data['type'] == 'ping') return; // Handled by WebSocketService

    if (data['type'] == 'message' && messageHandler != null) {
      final payload = data['payload'];
      if (payload is List) {
        for (final item in payload) {
          final msg = _normalizeMessageMap(item);
          if (msg != null) {
            _deliverWebSocketAgentMessage(msg);
          }
        }
      } else {
        final msg = _normalizeMessageMap(payload);
        if (msg != null) {
          _deliverWebSocketAgentMessage(msg);
        }
      }
    } else if (data['type'] == 'takeover') {
      handleTakeover();
    } else if (data['type'] == 'finalize') {
      handleConversationFinalized();
    }
  }

  void _deliverWebSocketAgentMessage(Map<String, dynamic> msg) {
    try {
      var adjusted = _adjustMessageTimestampsFromMap(msg);
      final idRaw = msg['message_id'] ?? msg['id'];
      if (adjusted.messageId == null && idRaw != null) {
        adjusted =
            adjusted.copyWith(messageId: _coerceOptionalStringId(idRaw));
      }
      if (adjusted.speaker != Speaker.customer) {
        messageHandler!(adjusted);
      }
    } catch (_) {
      // Malformed WS payloads must not tear down the app.
    }
  }

  static Map<String, dynamic>? _normalizeMessageMap(dynamic raw) {
    if (raw is Map<String, dynamic>) return raw;
    if (raw is Map) {
      try {
        return Map<String, dynamic>.from(raw);
      } catch (_) {
        return null;
      }
    }
    return null;
  }

  static String? _coerceOptionalStringId(dynamic v) {
    if (v == null) return null;
    if (v is String) return v;
    return v.toString();
  }

  static String _coerceSpeakerValue(dynamic v) {
    if (v is String && v.isNotEmpty) return v;
    if (v == null) return 'agent';
    return v.toString();
  }

  /// Inbound WS payloads may use odd speaker values; default unknown to agent
  /// so messages are not mistaken for customer (and skipped).
  static Speaker _speakerFromWebSocketField(dynamic v) {
    final s = _coerceSpeakerValue(v).toLowerCase();
    switch (s) {
      case 'customer':
        return Speaker.customer;
      case 'special':
        return Speaker.special;
      case 'agent':
      default:
        return Speaker.agent;
    }
  }

  static double _coerceTimestampField(dynamic v) {
    if (v == null) return 0;
    if (v is num) return v.toDouble();
    if (v is String) {
      try {
        return DateTime.parse(v).millisecondsSinceEpoch / 1000.0;
      } catch (_) {
        return 0;
      }
    }
    return 0;
  }

  static List<Attachment>? _attachmentsFromPayload(dynamic raw) {
    if (raw is! List) return null;
    final out = <Attachment>[];
    for (final e in raw) {
      final m = _normalizeMessageMap(e);
      if (m == null) continue;
      try {
        out.add(Attachment.fromJson(m));
      } catch (_) {}
    }
    return out.isEmpty ? null : out;
  }

  static List<MessageFeedback>? _feedbackFromPayload(dynamic raw) {
    if (raw is! List) return null;
    final out = <MessageFeedback>[];
    for (final e in raw) {
      final m = _normalizeMessageMap(e);
      if (m == null) continue;
      try {
        out.add(MessageFeedback.fromJson(m));
      } catch (_) {}
    }
    return out.isEmpty ? null : out;
  }

  /// Adjust message timestamps relative to conversation start.
  ChatMessage adjustMessageTimestamps(ChatMessage message) {
    if (_conversationCreateTime == null) return message;
    return message.copyWith(
      startTime: message.startTime - _conversationCreateTime!,
      endTime: message.endTime - _conversationCreateTime!,
    );
  }

  ChatMessage _adjustMessageTimestampsFromMap(Map<String, dynamic> msg) {
    var createTime = _coerceTimestampField(msg['create_time']);
    var startTime = _coerceTimestampField(msg['start_time']);
    var endTime = _coerceTimestampField(msg['end_time']);

    if (_conversationCreateTime != null) {
      startTime -= _conversationCreateTime!;
      endTime -= _conversationCreateTime!;
    }

    final idRaw = msg['message_id'] ?? msg['id'];

    return ChatMessage(
      createTime: createTime,
      startTime: startTime,
      endTime: endTime,
      speaker: _speakerFromWebSocketField(msg['speaker']),
      text: msg['text'] == null ? '' : msg['text'].toString(),
      messageId: _coerceOptionalStringId(idRaw),
      type: msg['type'] == null ? null : msg['type'].toString(),
      attachments: _attachmentsFromPayload(msg['attachments']),
      feedback: _feedbackFromPayload(msg['feedback']),
      linkUrl: msg['linkUrl'] == null ? null : msg['linkUrl'].toString(),
      linkLabel: msg['linkLabel'] == null ? null : msg['linkLabel'].toString(),
    );
  }

  // ── Heartbeat polling ──────────────────────────────────────────────

  /// Poll in-progress conversation (heartbeat when WS is disabled).
  Future<({String status, List<InProgressPollMessage> pollMessages})>
      pollInProgressConversation() async {
    if (_conversationId == null || _conversationCreateTime == null) {
      throw Exception('Conversation not started');
    }

    final uri = Uri.parse(
        '$baseUrl/api/conversations/in-progress/poll/$_conversationId');
    final response = await _httpClient.get(uri, headers: _getHeaders());

    if (response.statusCode != 200) {
      throw Exception('Poll failed: ${response.statusCode}');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final status = data['status'] as String;
    final rawMessages = data['messages'] as List<dynamic>? ?? [];

    final pollMessages = rawMessages.map((m) {
      final msg = m as Map<String, dynamic>;
      return _normalizePollMessage(msg);
    }).toList();

    return (status: status, pollMessages: pollMessages);
  }

  InProgressPollMessage _normalizePollMessage(Map<String, dynamic> m) {
    final rawCreateTime = m['create_time'];
    double createTime;
    if (rawCreateTime is num) {
      createTime = rawCreateTime.toDouble();
    } else if (rawCreateTime is String) {
      createTime = DateTime.parse(rawCreateTime).millisecondsSinceEpoch.toDouble();
    } else {
      createTime = (DateTime.now().millisecondsSinceEpoch / 1000).floorToDouble();
    }

    // Normalize to seconds: if >= 1e12 it's ms.
    if (createTime >= 1e12) {
      createTime = (createTime / 1000).roundToDouble();
    }

    final rawStartTime = (m['start_time'] as num?)?.toDouble() ?? 0;
    final rawEndTime = (m['end_time'] as num?)?.toDouble() ?? 0;

    final startTime = _conversationCreateTime != null
        ? createTime - _conversationCreateTime!
        : rawStartTime;
    final endTime = _conversationCreateTime != null
        ? startTime + (rawEndTime - rawStartTime == 0 ? 0.01 : rawEndTime - rawStartTime)
        : rawEndTime;

    return InProgressPollMessage(
      id: m['id'] as String,
      createTime: createTime,
      startTime: startTime,
      endTime: endTime,
      speaker: m['speaker'] as String,
      text: m['text'] as String? ?? '',
      type: m['type'] as String?,
      feedback: m['feedback'] != null
          ? (m['feedback'] as List<dynamic>)
              .map((e) => MessageFeedback.fromJson(e as Map<String, dynamic>))
              .toList()
          : null,
    );
  }

  /// Notify takeover from poll (handler only, no duplicate message).
  void notifyTakeoverFromPoll() {
    takeoverHandler?.call();
  }

  /// Notify finalized from poll (handler only, no duplicate message).
  void notifyFinalizedFromPoll() {
    finalizedHandler?.call();
    _isFinalized = true;
    _saveConversation();
  }

  /// Dispose the HTTP client.
  void dispose() {
    _httpClient.close();
  }
}
