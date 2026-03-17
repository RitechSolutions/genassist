import 'package:flutter/material.dart';
import 'package:gen_agent_chat/gen_agent_chat.dart';

void main() => runApp(const MyApp());

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GenAssist Chat Example',
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF6366F1),
        useMaterial3: true,
      ),
      home: const ChatExamplePage(),
    );
  }
}

class ChatExamplePage extends StatefulWidget {
  const ChatExamplePage({super.key});

  @override
  State<ChatExamplePage> createState() => _ChatExamplePageState();
}

class _ChatExamplePageState extends State<ChatExamplePage> {
  ChatMode _selectedMode = ChatMode.embedded;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('GenAssist Chat Example'),
        actions: [
          PopupMenuButton<ChatMode>(
            icon: const Icon(Icons.view_module),
            onSelected: (mode) => setState(() => _selectedMode = mode),
            itemBuilder: (_) => const [
              PopupMenuItem(
                value: ChatMode.embedded,
                child: Text('Embedded'),
              ),
              PopupMenuItem(
                value: ChatMode.floating,
                child: Text('Floating'),
              ),
              PopupMenuItem(
                value: ChatMode.fullscreen,
                child: Text('Fullscreen'),
              ),
            ],
          ),
        ],
      ),
      body: _buildChat(),
    );
  }

  Widget _buildChat() {
    return GenAgentChat(
      url: 'https://api.dev.genassist.ritech.io',
      apiKey: 'genagent123',
      metadata: const {
        'id': 'user-123',
        'name': 'John Doe',
        'email': 'john@example.com',
      },
      mode: _selectedMode,
      theme: const GenAgentChatTheme(
        primaryColor: Color(0xFF6366F1),
        secondaryColor: Color(0xFF818CF8),
      ),
      headerTitle: 'Support',
      description: 'How can we help you?',
      useWs: false,
      useFile: true,
      useAudio: false,
      language: 'en',
      showWelcomeBeforeStart: true,
      onError: (error) => debugPrint('Chat error: $error'),
      onTakeover: () => debugPrint('Chat taken over by human'),
      onFinalize: () => debugPrint('Chat finalized'),
    );
  }
}
