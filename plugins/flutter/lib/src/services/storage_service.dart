/// Wraps SharedPreferences for conversation persistence.
/// Ported from the localStorage logic in React chatService.ts.

import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/chat_message.dart';
import '../models/api_responses.dart';

class StorageService {
  static const _storageKeyBase = 'genassist_conversation';
  final String apiKey;
  /// Optional tenant id; when set, keys are namespaced like iOS
  /// `keySuffix` (`_tenant_<id>`) so conversations do not collide across tenants.
  final String? tenant;

  StorageService({required this.apiKey, this.tenant});

  /// Suffix appended to storage keys, matching [GenassistChatIOS/ChatService.keySuffix].
  String get _keySuffix {
    final t = tenant;
    if (t == null || t.trim().isEmpty) return '';
    return '_tenant_${t.trim()}';
  }

  bool get _scopedByTenant => _keySuffix.isNotEmpty;

  String get _storageKey => '$_storageKeyBase:$apiKey$_keySuffix';

  String _messagesKey(String conversationId) =>
      'genassist_conversation_messages:$apiKey$_keySuffix:$conversationId';

  /// Save the current conversation metadata to SharedPreferences.
  Future<void> saveConversation({
    required String conversationId,
    required double createTime,
    required bool isFinalized,
    required List<String> possibleQueries,
    required AgentWelcomeData welcomeData,
    required AgentThinkingConfig thinkingConfig,
    String? agentId,
    String? guestToken,
    List<String>? availableLanguages,
  }) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final data = {
        'conversationId': conversationId,
        'createTime': createTime,
        'isFinalized': isFinalized,
        'possibleQueries': possibleQueries,
        'welcomeData': welcomeData.toJson(),
        'thinkingConfig': {
          'phrases': thinkingConfig.phrases,
          'delayMs': thinkingConfig.delayMs,
        },
        if (agentId != null) 'agentId': agentId,
        if (guestToken != null) 'guestToken': guestToken,
        if (availableLanguages != null)
          'availableLanguages': availableLanguages,
      };
      await prefs.setString(_storageKey, jsonEncode(data));
    } catch (_) {
      // ignore
    }
  }

  /// Load a previously saved conversation from SharedPreferences.
  /// Returns null if nothing is saved.
  Future<Map<String, dynamic>?> loadSavedConversation() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      String? raw = prefs.getString(_storageKey);
      // Backward-compat: legacy keys without apiKey/tenant scope only when not tenant-scoped.
      if (raw == null && !_scopedByTenant) {
        raw = prefs.getString(_storageKeyBase);
      }
      if (raw == null) return null;
      final parsed = jsonDecode(raw) as Map<String, dynamic>;
      return parsed;
    } catch (_) {
      return null;
    }
  }

  /// Persist chat messages for a specific conversation.
  Future<void> saveMessages(
      String conversationId, List<ChatMessage> messages) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final key = _messagesKey(conversationId);
      final encoded = jsonEncode(messages.map((m) => m.toJson()).toList());
      await prefs.setString(key, encoded);
    } catch (_) {
      // ignore
    }
  }

  /// Load persisted messages for a conversation.
  Future<List<ChatMessage>> loadMessages(String conversationId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final key = _messagesKey(conversationId);
      final raw = prefs.getString(key);
      if (raw == null) return [];
      final list = jsonDecode(raw) as List<dynamic>;
      return list
          .map((e) => ChatMessage.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (_) {
      return [];
    }
  }

  /// Clear the conversation metadata from SharedPreferences.
  Future<void> clearConversation() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_storageKey);
    } catch (_) {
      // ignore
    }
  }

  /// Clear persisted messages for a specific conversation.
  Future<void> clearMessages(String conversationId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final key = _messagesKey(conversationId);
      await prefs.remove(key);
    } catch (_) {
      // ignore
    }
  }
}
