/// ChangeNotifier that manages all chat state.
/// Ported from React useChat.ts.

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/chat_message.dart';
import '../models/api_responses.dart';
import '../services/chat_service.dart';
import '../services/websocket_service.dart';
import '../services/storage_service.dart';

/// Default messages when server is unreachable.
const String _defaultServerUnavailableMessage =
    'The service is temporarily unavailable. Please try again later.';
const String _defaultServerUnavailableContactLabel = 'Contact support';

/// Check whether an error is likely a network / 5xx server error.
bool _isNetworkOrServerError(Object error) {
  final msg = error.toString().toLowerCase();
  return msg.contains('socketexception') ||
      msg.contains('handshakeexception') ||
      msg.contains('connection refused') ||
      msg.contains('connection reset') ||
      msg.contains('connection closed') ||
      msg.contains('timeout') ||
      msg.contains('network is unreachable') ||
      msg.contains('status 5');
}

class ChatState extends ChangeNotifier {
  // ── Configuration (immutable after construction) ───────────────────
  final String baseUrl;
  final String? websocketUrl;
  final String apiKey;
  final String? tenant;
  final Map<String, dynamic>? metadata;
  final bool useWs;
  final bool usePoll;
  final String? serverUnavailableMessage;
  final String? serverUnavailableContactUrl;
  final String? serverUnavailableContactLabel;

  // External callbacks
  final void Function(Object error)? onError;
  final void Function()? onTakeover;
  final void Function()? onFinalize;
  final void Function(Map<String, dynamic>? chatInputMetadata)? onConfigLoaded;

  // ── Services ───────────────────────────────────────────────────────
  late final ChatService _chatService;
  late final WebSocketService _wsService;
  late final StorageService _storageService;
  StreamSubscription<Map<String, dynamic>>? _wsMessageSub;
  StreamSubscription<ConnectionState>? _wsStateSub;

  // ── Observable state ───────────────────────────────────────────────
  List<ChatMessage> _messages = [];
  bool _isLoading = false;
  ConnectionState _connectionState = ConnectionState.disconnected;
  String? _conversationId;
  String? _guestToken;
  bool _isAgentTyping = false;
  bool _isTakenOver = false;
  bool _isFinalized = false;
  List<String> _possibleQueries = [];
  String? _welcomeTitle;
  String? _welcomeImageUrl;
  String? _welcomeMessage;
  String? _inputDisclaimerHtml;
  List<String> _thinkingPhrases = [];
  int _thinkingDelayMs = 1000;
  List<String>? _availableLanguages;
  Map<String, dynamic> _chatInputMetadata = {};
  List<Attachment> _preloadedAttachments = [];
  String _language = 'en';

  /// When true, [notifyListeners] is skipped (e.g. after [dispose]) so async
  /// [init] cannot fire notifications on a disposed notifier.
  bool _notificationsMuted = false;

  void _notify() {
    if (_notificationsMuted) return;
    notifyListeners();
  }

  // ── Heartbeat polling state ────────────────────────────────────────
  Timer? _heartbeatTimer;
  int _heartbeatFailureCount = 0;
  int _heartbeatInterval = 0;
  double _lastServerCreateTime = 0;
  bool _takeoverProcessed = false;
  bool _finalizedProcessed = false;

  static const int _heartbeatInitialIntervalMs = 2000;
  static const int _heartbeatIntervalStepMs = 5000;
  static const int _heartbeatMaxIntervalMs = 30000;
  static const int _heartbeatMaxFailures = 5;

  // ── Getters ────────────────────────────────────────────────────────
  List<ChatMessage> get messages => List.unmodifiable(_messages);
  bool get isLoading => _isLoading;
  ConnectionState get connectionState => _connectionState;
  String? get conversationId => _conversationId;
  String? get guestToken => _guestToken;
  bool get isAgentTyping => _isAgentTyping;
  bool get isTakenOver => _isTakenOver;
  bool get isFinalized => _isFinalized;
  List<String> get possibleQueries => List.unmodifiable(_possibleQueries);
  String? get welcomeTitle => _welcomeTitle;
  String? get welcomeImageUrl => _welcomeImageUrl;
  String? get welcomeMessage => _welcomeMessage;
  String? get inputDisclaimerHtml => _inputDisclaimerHtml;
  List<String> get thinkingPhrases => List.unmodifiable(_thinkingPhrases);
  int get thinkingDelayMs => _thinkingDelayMs;
  String get currentLanguage => _language;
  List<String>? get availableLanguages =>
      _availableLanguages != null ? List.unmodifiable(_availableLanguages!) : null;
  Map<String, dynamic> get chatInputMetadata =>
      Map.unmodifiable(_chatInputMetadata);
  List<Attachment> get preloadedAttachments =>
      List.unmodifiable(_preloadedAttachments);

  // ── Constructor ────────────────────────────────────────────────────
  ChatState({
    required this.baseUrl,
    this.websocketUrl,
    required this.apiKey,
    this.tenant,
    this.metadata,
    this.useWs = true,
    this.usePoll = false,
    String? language,
    this.serverUnavailableMessage,
    this.serverUnavailableContactUrl,
    this.serverUnavailableContactLabel,
    this.onError,
    this.onTakeover,
    this.onFinalize,
    this.onConfigLoaded,
  }) {
    _language = language ?? 'en';
    _storageService = StorageService(apiKey: apiKey);

    _chatService = ChatService(
      baseUrl: baseUrl,
      websocketUrl: websocketUrl,
      apiKey: apiKey,
      metadata: metadata,
      tenant: tenant,
      language: _language,
      useWs: useWs,
      usePoll: usePoll,
    );

    _wsService = WebSocketService(
      baseUrl: baseUrl,
      websocketUrl: websocketUrl,
      apiKey: apiKey,
      tenant: tenant,
      useWs: useWs,
    );

    _chatService.serverUnavailableMessage = serverUnavailableMessage;
    _chatService.serverUnavailableContactUrl = serverUnavailableContactUrl;
    _chatService.serverUnavailableContactLabel = serverUnavailableContactLabel;
  }

  // ── Initialization ─────────────────────────────────────────────────

  /// Async init: load saved conversation, set up handlers, fetch agent info.
  /// Call this after construction (e.g. in the widget's initState).
  Future<void> init() async {
    _setupChatServiceHandlers();
    _setupWebSocketListeners();

    // Load saved conversation
    await _chatService.loadSavedConversation();

    final convId = _chatService.conversationId;
    if (convId != null) {
      _conversationId = convId;
      _guestToken = _chatService.guestToken;
      if (_chatService.isFinalized) {
        _isFinalized = true;
      } else if (!useWs) {
        _connectionState = ConnectionState.connected;
      }

      // Load persisted messages
      final savedMessages = await _storageService.loadMessages(convId);
      if (savedMessages.isNotEmpty) {
        _messages = savedMessages;
        _validateMessages();
        _lastServerCreateTime = _messages.fold<double>(
          0,
          (max, m) => m.createTime > max ? m.createTime : max,
        );
      }

      // Connect WS if applicable
      if (useWs && !_isFinalized) {
        _wsService.connect(convId, _guestToken);
      }
    }

    // Pull initial static data from loaded conversation
    _syncWelcomeData();

    // Fetch agent info
    final info = await _chatService.fetchAgentInfo();
    if (info != null && info.agentAvailableLanguages != null) {
      _availableLanguages = info.agentAvailableLanguages;
    }

    onConfigLoaded?.call(_chatService.chatInputMetadata);

    // Start heartbeat polling if needed
    if (!useWs && usePoll && _conversationId != null && !_isFinalized) {
      _startHeartbeatPolling();
    }

    _notify();
  }

  // ── Chat service handler setup ─────────────────────────────────────

  void _setupChatServiceHandlers() {
    _chatService.messageHandler = _onChatMessage;

    _chatService.takeoverHandler = () {
      _isTakenOver = true;
      _isAgentTyping = false;
      onTakeover?.call();
      _notify();
    };

    _chatService.finalizedHandler = () {
      _isFinalized = true;
      _isAgentTyping = false;
      onFinalize?.call();
      _notify();
    };

    _chatService.connectionStateHandler = (state) {
      switch (state) {
        case 'connecting':
          _connectionState = ConnectionState.connecting;
          break;
        case 'connected':
          _connectionState = ConnectionState.connected;
          break;
        default:
          _connectionState = ConnectionState.disconnected;
          _isAgentTyping = false;
      }
      _notify();
    };

    _chatService.welcomeDataHandler = (data) {
      _welcomeTitle = data.title;
      _welcomeImageUrl = data.imageUrl;
      _welcomeMessage = data.message;
      _inputDisclaimerHtml = data.inputDisclaimerHtml;
      if (data.possibleQueries.isNotEmpty) {
        _possibleQueries = data.possibleQueries;
      }
      _notify();
    };
  }

  void _setupWebSocketListeners() {
    _wsMessageSub = _wsService.messageStream.listen((data) {
      try {
        _chatService.processWebSocketMessage(data);
      } catch (e, _) {
        onError?.call(e);
      }
    });

    _wsStateSub = _wsService.connectionStateStream.listen((state) {
      _connectionState = state;
      if (state != ConnectionState.connected) {
        _isAgentTyping = false;
      }
      _notify();
    });
  }

  /// Handle an incoming message from ChatService.
  void _onChatMessage(ChatMessage message) {
    final normalized = message.copyWith(
      createTime: (message.createTime <= 0 || message.createTime.isNaN)
          ? DateTime.now().millisecondsSinceEpoch / 1000.0
          : message.createTime,
    );

    // Track latest create_time
    if (normalized.createTime > 0) {
      _lastServerCreateTime = normalized.createTime;
    }

    // Deduplicate by message_id, but allow richer late updates to replace
    // a previously stored placeholder/empty message.
    if (normalized.messageId != null) {
      final existingIndex = _messages.indexWhere(
        (m) => m.messageId == normalized.messageId,
      );
      if (existingIndex != -1) {
        final existing = _messages[existingIndex];
        final shouldReplace =
            (existing.text.trim().isEmpty && normalized.text.trim().isNotEmpty) ||
            ((existing.attachments == null || existing.attachments!.isEmpty) &&
                (normalized.attachments != null &&
                    normalized.attachments!.isNotEmpty)) ||
            (existing.type == null && normalized.type != null);
        if (!shouldReplace) return;
        _messages = [
          ..._messages.sublist(0, existingIndex),
          normalized,
          ..._messages.sublist(existingIndex + 1),
        ];
      } else {
        _messages = [..._messages, normalized];
      }
    } else {
      _messages = [..._messages, normalized];
    }

    // Stop typing when agent/special message arrives
    if (normalized.speaker == Speaker.agent ||
        normalized.speaker == Speaker.special) {
      _isAgentTyping = false;
    }

    _validateMessages();
    _persistMessages();
    _notify();
  }

  /// Detect takeover / finalized from message list.
  void _validateMessages() {
    if (!_isTakenOver) {
      _isTakenOver = _messages.any((m) => m.type == 'takeover');
    }
    if (!_isFinalized) {
      _isFinalized = _messages.any((m) => m.type == 'finalized');
    }
  }

  /// Persist messages to storage.
  void _persistMessages() {
    if (_conversationId == null) return;
    _storageService.saveMessages(_conversationId!, _messages);
  }

  /// Sync welcome/thinking data from chat service into state fields.
  void _syncWelcomeData() {
    final queries = _chatService.possibleQueries;
    if (queries.isNotEmpty) _possibleQueries = queries;

    final welcome = _chatService.welcomeData;
    _welcomeTitle = welcome.title;
    _welcomeImageUrl = welcome.imageUrl;
    _welcomeMessage = welcome.message;
    _inputDisclaimerHtml = welcome.inputDisclaimerHtml;

    final thinking = _chatService.thinkingConfig;
    _thinkingPhrases = thinking.phrases;
    _thinkingDelayMs = thinking.delayMs;

    final meta = _chatService.chatInputMetadata;
    if (meta.isNotEmpty) _chatInputMetadata = meta;

    final langs = _chatService.availableLanguages;
    if (langs != null) _availableLanguages = langs;
  }

  // ── Reset to initial state (e.g. after token expiration) ───────────

  void _resetToInitialState() {
    _conversationId = null;
    _guestToken = null;
    _isFinalized = false;
    _isTakenOver = false;
    _connectionState = ConnectionState.disconnected;
    _welcomeTitle = null;
    _welcomeImageUrl = null;
    _welcomeMessage = null;
    _inputDisclaimerHtml = null;
    _possibleQueries = [];
    _thinkingPhrases = [];
    _thinkingDelayMs = 1000;
    _chatInputMetadata = {};
    _messages = [];
    _lastServerCreateTime = 0;
    _isAgentTyping = false;
    _preloadedAttachments = [];
    _stopHeartbeatPolling();
    _wsService.disconnect();
    _notify();
  }

  // ── Public actions ─────────────────────────────────────────────────

  /// Start a new conversation.
  Future<void> startConversation({String? reCaptchaToken}) async {
    _connectionState = ConnectionState.connecting;
    _isLoading = true;
    _messages = [];
    _possibleQueries = [];
    _welcomeTitle = null;
    _welcomeImageUrl = null;
    _welcomeMessage = null;
    _inputDisclaimerHtml = null;
    _thinkingPhrases = [];
    _thinkingDelayMs = 1000;
    _lastServerCreateTime = 0;
    _isFinalized = false;
    _isTakenOver = false;
    _isAgentTyping = false;
    _preloadedAttachments = [];
    _notify();

    try {
      _stopHeartbeatPolling();
      _wsService.disconnect();

      if (_conversationId != null) {
        await _storageService.clearMessages(_conversationId!);
      }
      await _chatService.resetChatConversation();
      _conversationId = null;
      _guestToken = null;

      final convId =
          await _chatService.startConversation(reCaptchaToken: reCaptchaToken);
      _conversationId = convId;
      _guestToken = _chatService.guestToken;
      _connectionState = ConnectionState.connected;

      _syncWelcomeData();

      onConfigLoaded?.call(_chatService.chatInputMetadata);

      // Connect WS
      if (useWs) {
        _wsService.connect(convId, _guestToken);
      } else if (usePoll) {
        _startHeartbeatPolling();
      }
    } catch (error) {
      _connectionState = ConnectionState.disconnected;
      _isAgentTyping = false;
      if (onError != null && error is Exception) {
        onError!(error);
      }
    } finally {
      _isLoading = false;
      _notify();
    }
  }

  /// Reset and start a new conversation.
  Future<void> resetConversation({String? reCaptchaToken}) async {
    await startConversation(reCaptchaToken: reCaptchaToken);
  }

  /// Send a message in the current conversation.
  Future<void> sendMessage(
    String text, {
    List<dynamic>? files,
    Map<String, dynamic>? extraMetadata,
    String? reCaptchaToken,
  }) async {
    // Prevent concurrent sends while agent is still responding.
    if (_isAgentTyping || _isLoading || _isFinalized) {
      return;
    }
    try {
      _isLoading = true;
      _notify();

      // Match pre-uploaded attachments by name/size
      final newAttachments = <Attachment>[];
      if (files != null && files.isNotEmpty) {
        for (final f in files) {
          // files may be File / PlatformFile / identifiers.
          // Match against both path basename and explicit file name.
          final candidates = _fileNames(f);
          final match = _preloadedAttachments.cast<Attachment?>().firstWhere(
                (pa) => pa != null && candidates.contains(pa.name),
                orElse: () => null,
              );
          if (match != null) newAttachments.add(match);
        }
        // Fallback: if uploads exist but strict matching failed, attach all
        // preloaded files to avoid empty message bubbles.
        if (newAttachments.isEmpty && _preloadedAttachments.isNotEmpty) {
          newAttachments.addAll(_preloadedAttachments);
        }
      }

      if (!_isTakenOver) {
        _isAgentTyping = true;
        _notify();
      }

      await _chatService.sendMessage(
        text,
        attachments: newAttachments.isNotEmpty ? newAttachments : null,
        extraMetadata: extraMetadata,
        reCaptchaToken: reCaptchaToken,
      );

      // In request/response mode (no WS and no polling), some backends may not
      // include an agent message in the update response. Avoid an infinite
      // "Thinking..." state in that case.
      if (!useWs && !usePoll) {
        _isAgentTyping = false;
      }

      _preloadedAttachments = [];
    } catch (error) {
      _isAgentTyping = false;
      if (_isTokenExpired(error)) {
        _resetToInitialState();
      } else if (_isNetworkOrServerError(error)) {
        _injectServerUnavailableMessage();
      } else if (onError != null) {
        onError!(error);
      }
    } finally {
      _isLoading = false;
      _notify();
    }
  }

  /// Upload a file and track it as a preloaded attachment.
  Future<Attachment?> uploadFile(dynamic file) async {
    if (_conversationId == null) return null;

    try {
      // file is expected to be dart:io File
      final uploadResult =
          await _chatService.uploadFile(_conversationId!, file);
      if (uploadResult == null) return null;

      final fileUrl = Uri.parse(baseUrl).resolve(uploadResult.fileUrl).toString();
      final attachment = Attachment(
        name: uploadResult.originalFilename,
        type: '', // MIME type not reliably available from upload response
        size: 0,
        url: fileUrl,
        fileId: uploadResult.fileId,
      );

      _preloadedAttachments = [..._preloadedAttachments, attachment];
      _notify();
      return attachment;
    } catch (error) {
      if (_isTokenExpired(error)) {
        _resetToInitialState();
      }
      onError?.call(error);
      return null;
    }
  }

  /// Add feedback to an agent message.
  Future<void> addFeedback(
    String messageId,
    String value, {
    String? feedbackMessage,
  }) async {
    if (messageId.isEmpty) return;

    try {
      await _chatService.addFeedback(
        messageId,
        value,
        feedbackMessage: feedbackMessage,
      );

      final newFeedback = MessageFeedback(
        feedback: value,
        feedbackMessage: feedbackMessage,
        feedbackTimestamp: DateTime.now().toUtc().toIso8601String(),
      );

      _messages = _messages.map((m) {
        final msgId = m.messageId;
        if (msgId == messageId) {
          return m.copyWith(
            feedback: [...(m.feedback ?? []), newFeedback],
          );
        }
        return m;
      }).toList();

      _persistMessages();
      _notify();
    } catch (error) {
      onError?.call(error);
    }
  }

  /// Update the language for the chat.
  void setLanguage(String language) {
    _language = language;
    _chatService.language = language;
    _wsService.setLanguage(language);
  }

  // ── Heartbeat polling ──────────────────────────────────────────────

  void _startHeartbeatPolling() {
    _stopHeartbeatPolling();
    _heartbeatFailureCount = 0;
    _heartbeatInterval = _heartbeatInitialIntervalMs;
    _takeoverProcessed = false;
    _finalizedProcessed = false;
    _schedulePoll(_heartbeatInitialIntervalMs);
  }

  void _stopHeartbeatPolling() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = null;
  }

  void _schedulePoll(int delayMs) {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer(Duration(milliseconds: delayMs), _poll);
  }

  Future<void> _poll() async {
    if (_conversationId == null || _isFinalized) return;

    try {
      final result = await _chatService.pollInProgressConversation();
      _heartbeatFailureCount = 0;

      final lastCt = _lastServerCreateTime.floor();
      final newMessagesRaw = result.pollMessages.where((m) {
        final ct = m.createTime is num ? (m.createTime as num).toDouble() : 0.0;
        return ct > 0 && ct.isFinite && ct > lastCt;
      }).toList();

      if (newMessagesRaw.isNotEmpty) {
        final newMessages = newMessagesRaw.map((m) {
          String speakerStr;
          if (m.speaker == 'customer') {
            speakerStr = 'customer';
          } else if (m.speaker == 'agent') {
            speakerStr = 'agent';
          } else {
            speakerStr = 'special';
          }

          String text;
          if (m.type == 'takeover') {
            text = 'Supervisor took over';
          } else if (m.type == 'finalized') {
            text = 'Conversation Finalized';
          } else {
            text = m.text;
          }

          return ChatMessage(
            messageId: m.id,
            createTime: m.createTime is num ? (m.createTime as num).toDouble() : 0,
            startTime: m.startTime,
            endTime: m.endTime,
            speaker: SpeakerExtension.fromJson(speakerStr),
            text: text,
            type: m.type,
            feedback: m.feedback,
          );
        }).toList();

        // Deduplicate
        final existingIds = _messages
            .map((m) => m.messageId)
            .where((id) => id != null)
            .toSet();
        final toAdd = newMessages
            .where((m) => m.messageId == null || !existingIds.contains(m.messageId))
            .toList();

        if (toAdd.isNotEmpty) {
          final maxCt = toAdd.fold<double>(
            _lastServerCreateTime,
            (max, m) => m.createTime.isFinite && m.createTime > max ? m.createTime : max,
          );
          _lastServerCreateTime = maxCt;
          _messages = [..._messages, ...toAdd];
          _persistMessages();
          // Reset typing on agent messages
          if (toAdd.any((m) =>
              m.speaker == Speaker.agent || m.speaker == Speaker.special)) {
            _isAgentTyping = false;
          }
        }

        // Check for takeover/finalized
        final hasTakeover = newMessages.any((m) => m.type == 'takeover');
        final hasFinalized = newMessages.any((m) => m.type == 'finalized');

        if ((result.status == 'finalized' || hasFinalized) &&
            !_finalizedProcessed) {
          _finalizedProcessed = true;
          _isFinalized = true;
          onFinalize?.call();
        } else if ((result.status == 'takeover' || hasTakeover) &&
            !_takeoverProcessed) {
          _takeoverProcessed = true;
          _isTakenOver = true;
          onTakeover?.call();
        }
      } else {
        // No new messages, but check status
        if (result.status == 'finalized' && !_finalizedProcessed) {
          _finalizedProcessed = true;
          _chatService.handleConversationFinalized();
          _isFinalized = true;
        } else if (result.status == 'takeover' && !_takeoverProcessed) {
          _takeoverProcessed = true;
          _chatService.notifyTakeoverFromPoll();
          _isTakenOver = true;
        }
      }

      _notify();

      if (result.status == 'finalized') return; // Stop polling

      _heartbeatInterval = _heartbeatIntervalStepMs;
      _schedulePoll(_heartbeatInterval);
    } catch (_) {
      _heartbeatFailureCount++;
      if (_heartbeatFailureCount >= _heartbeatMaxFailures) return;
      _schedulePoll(_heartbeatInterval > 0
          ? _heartbeatInterval
          : _heartbeatInitialIntervalMs);
    }
  }

  // ── Helpers ────────────────────────────────────────────────────────

  bool _isTokenExpired(Object error) {
    return error.toString().contains('Token has expired');
  }

  void _injectServerUnavailableMessage() {
    final now = DateTime.now().millisecondsSinceEpoch / 1000.0;
    final createTime = _chatService.conversationCreateTime;
    final startTime = createTime != null ? now - createTime : 0.0;
    final endTime = startTime + 0.01;

    final msg = ChatMessage(
      createTime: now,
      startTime: startTime,
      endTime: endTime,
      speaker: Speaker.special,
      text: serverUnavailableMessage ?? _defaultServerUnavailableMessage,
      linkUrl: serverUnavailableContactUrl,
      linkLabel: serverUnavailableContactLabel ?? _defaultServerUnavailableContactLabel,
    );

    _messages = [..._messages, msg];
    _persistMessages();
    _notify();
  }

  /// Extract possible file names from a dynamic file object.
  List<String> _fileNames(dynamic file) {
    if (file is String) return [file];
    final names = <String>{};
    try {
      final name = (file as dynamic).name;
      if (name != null && name.toString().isNotEmpty) {
        names.add(name.toString());
      }
    } catch (_) {
      // ignore
    }
    try {
      final path = (file as dynamic).path;
      if (path != null && path.toString().isNotEmpty) {
        names.add(path.toString().split('/').last);
      }
    } catch (_) {
      // ignore
    }
    return names.toList();
  }

  // ── Dispose ────────────────────────────────────────────────────────

  @override
  void dispose() {
    _notificationsMuted = true;
    _stopHeartbeatPolling();
    _wsMessageSub?.cancel();
    _wsStateSub?.cancel();
    _wsService.dispose();
    _chatService.dispose();
    super.dispose();
  }
}
