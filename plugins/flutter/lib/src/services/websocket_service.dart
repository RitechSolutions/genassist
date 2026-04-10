/// WebSocket service for real-time chat communication.
/// Ported from React useChatWebSocket.ts.

import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

/// Represents the state of the WebSocket connection.
enum ConnectionState { connecting, connected, disconnected }

class WebSocketService {
  // ── Configuration ──────────────────────────────────────────────────
  final String baseUrl;
  final String? websocketUrl;
  final String apiKey;
  final String? tenant;
  final bool useWs;
  final int maxReconnectAttempts;
  final int reconnectBaseDelayMs;

  // ── Internal state ─────────────────────────────────────────────────
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _channelSubscription;
  int _reconnectAttempts = 0;
  Timer? _reconnectTimer;
  String? _conversationId;
  String? _guestToken;
  String _language = 'en';
  bool _disposed = false;
  bool _intentionalDisconnect = false;

  // ── Stream controllers ─────────────────────────────────────────────
  final _messageController =
      StreamController<Map<String, dynamic>>.broadcast();
  final _connectionStateController =
      StreamController<ConnectionState>.broadcast();

  /// Stream of parsed WebSocket messages (JSON objects).
  Stream<Map<String, dynamic>> get messageStream => _messageController.stream;

  /// Stream of connection state changes.
  Stream<ConnectionState> get connectionStateStream =>
      _connectionStateController.stream;

  ConnectionState _currentState = ConnectionState.disconnected;

  /// The current connection state.
  ConnectionState get currentState => _currentState;

  // ── Constructor ────────────────────────────────────────────────────
  WebSocketService({
    required String baseUrl,
    this.websocketUrl,
    required this.apiKey,
    this.tenant,
    this.useWs = true,
    this.maxReconnectAttempts = 5,
    this.reconnectBaseDelayMs = 1000,
  }) : baseUrl =
            baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;

  // ── Public methods ─────────────────────────────────────────────────

  /// Open a WebSocket connection for the given conversation.
  void connect(String conversationId, String? guestToken) {
    if (_disposed || !useWs) return;

    _conversationId = conversationId;
    _guestToken = guestToken;
    _intentionalDisconnect = false;

    // Close any existing connection
    _closeChannel();

    final wsUrl = _buildWebSocketUrl(conversationId);
    _updateConnectionState(ConnectionState.connecting);

    try {
      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));

      _channelSubscription = _channel!.stream.listen(
        _onData,
        onError: _onError,
        onDone: _onDone,
      );

      // WebSocketChannel.connect reports open via the stream becoming active.
      // We transition to connected on first successful listen.
      _reconnectAttempts = 0;
      _updateConnectionState(ConnectionState.connected);
    } catch (e) {
      _updateConnectionState(ConnectionState.disconnected);
      _scheduleReconnect();
    }
  }

  /// Disconnect the WebSocket (intentional close, no reconnect).
  void disconnect() {
    _intentionalDisconnect = true;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _reconnectAttempts = 0;
    _closeChannel();
    _updateConnectionState(ConnectionState.disconnected);
  }

  /// Update the language used in the WebSocket URL.
  void setLanguage(String language) {
    _language = language;
  }

  /// Clean up all resources. Call when the service is no longer needed.
  void dispose() {
    _disposed = true;
    disconnect();
    _messageController.close();
    _connectionStateController.close();
  }

  // ── Private helpers ────────────────────────────────────────────────

  void _closeChannel() {
    _channelSubscription?.cancel();
    _channelSubscription = null;
    try {
      _channel?.sink.close();
    } catch (_) {}
    _channel = null;
  }

  void _updateConnectionState(ConnectionState state) {
    if (_currentState == state) return;
    _currentState = state;
    if (!_connectionStateController.isClosed) {
      _connectionStateController.add(state);
    }
  }

  /// Build the WebSocket URL matching the React implementation.
  String _buildWebSocketUrl(String conversationId) {
    final topics = ['message', 'takeover', 'finalize'];
    final topicsQuery = topics.map((t) => 'topics=$t').join('&');
    final langParam = '&lang=$_language';

    final authParam = _guestToken != null && _guestToken!.isNotEmpty
        ? 'access_token=${Uri.encodeComponent(_guestToken!)}'
        : 'api_key=${Uri.encodeComponent(apiKey)}';

    final tenantParam = tenant != null
        ? '&x-tenant-id=${Uri.encodeComponent(tenant!)}'
        : '';

    // New websocket service
    if (websocketUrl != null && websocketUrl!.isNotEmpty) {
      final wsBase = websocketUrl!.endsWith('/')
          ? websocketUrl!.substring(0, websocketUrl!.length - 1)
          : websocketUrl!;
      return '$wsBase/ws/conversations/$conversationId?$authParam$langParam&$topicsQuery$tenantParam';
    }

    // Legacy: derive WS URL from HTTP URL
    final wsBase = baseUrl.replaceFirst('http', 'ws');
    return '$wsBase/api/conversations/ws/$conversationId?$authParam$langParam&$topicsQuery$tenantParam';
  }

  void _onData(dynamic rawData) {
    final text = _decodeSocketFrame(rawData);
    if (text == null) return;

    try {
      final decoded = jsonDecode(text);
      if (decoded is! Map) return;
      final data = decoded is Map<String, dynamic>
          ? decoded
          : Map<String, dynamic>.from(decoded as Map);

      // Respond to server ping with pong (keep-alive).
      if (data['type'] == 'ping') {
        _sendPong();
        return;
      }

      if (!_messageController.isClosed) {
        _messageController.add(data);
      }
    } catch (_) {
      // Ignore parse errors
    }
  }

  String? _decodeSocketFrame(dynamic rawData) {
    if (rawData is String) return rawData;
    if (rawData is List<int>) {
      try {
        return utf8.decode(rawData);
      } catch (_) {
        return null;
      }
    }
    return null;
  }

  void _sendPong() {
    try {
      _channel?.sink.add(jsonEncode({'type': 'pong'}));
    } catch (_) {
      // ignore
    }
  }

  void _onError(Object error) {
    _updateConnectionState(ConnectionState.disconnected);
    _scheduleReconnect();
  }

  void _onDone() {
    _updateConnectionState(ConnectionState.disconnected);

    // The channel is done (closed). Attempt reconnect if not intentional.
    if (!_intentionalDisconnect && !_disposed) {
      _scheduleReconnect();
    }
  }

  /// Schedule a reconnect with exponential backoff (max 30 seconds, max N attempts).
  void _scheduleReconnect() {
    if (_disposed || _intentionalDisconnect) return;
    if (_reconnectAttempts >= maxReconnectAttempts) return;
    if (_conversationId == null) return;

    _reconnectAttempts++;
    final delay = Duration(
      milliseconds: _clampDelay(
        reconnectBaseDelayMs * _pow2(_reconnectAttempts - 1),
        30000,
      ),
    );

    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(delay, () {
      _reconnectTimer = null;
      if (!_disposed && !_intentionalDisconnect && _conversationId != null) {
        connect(_conversationId!, _guestToken);
      }
    });
  }

  static int _pow2(int exponent) {
    int result = 1;
    for (int i = 0; i < exponent; i++) {
      result *= 2;
    }
    return result;
  }

  static int _clampDelay(int value, int max) => value > max ? max : value;
}
