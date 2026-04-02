# GenAssist Chat - Flutter Plugin

A Flutter chat widget for GenAssist AI agents. Supports WebSocket/HTTP messaging, file uploads, voice input, interactive content, and internationalization (6 languages).

## Installation

Add to your `pubspec.yaml`:

```yaml
dependencies:
  gen_agent_chat:
    path: ../  # or git/pub reference
```

## Quick Start

```dart
import 'package:gen_agent_chat/gen_agent_chat.dart';

GenAgentChat(
  url: 'https://your-api-url.com',
  apiKey: 'your-api-key',
  metadata: {'id': 'user-123', 'name': 'John Doe'},
  mode: ChatMode.embedded,
  useWs: true,
)
```

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `String` | required | Base API URL |
| `apiKey` | `String` | required | API key |
| `metadata` | `Map<String, dynamic>?` | `null` | User metadata |
| `mode` | `ChatMode` | `embedded` | `embedded`, `floating`, or `fullscreen`. **Floating:** bubble opens a **full-screen modal** (not an inline panel). **Fullscreen:** fills the parent. |
| `onClose` | `VoidCallback?` | `null` | Optional header close button; after a floating modal closes, this is called once. |
| `theme` | `GenAgentChatTheme?` | `null` | Colors, fonts, sizing |
| `headerTitle` | `String?` | `null` | Header bar title |
| `description` | `String?` | `null` | Header subtitle |
| `placeholder` | `String?` | `null` | Input field placeholder |
| `useWs` | `bool` | `true` | Enable WebSocket |
| `usePoll` | `bool` | `false` | Enable HTTP polling fallback |
| `useFile` | `bool` | `false` | Enable file attachments |
| `useAudio` | `bool` | `false` | Enable voice input |
| `language` | `String?` | `null` | UI language (en, es, fr, de, it, pt) |
| `showWelcomeBeforeStart` | `bool` | `true` | Show welcome card |
| `onError` | `Function(String)?` | `null` | Error callback |
| `onTakeover` | `Function()?` | `null` | Human takeover callback |
| `onFinalize` | `Function()?` | `null` | Chat finalized callback |

## Theming

```dart
GenAgentChatTheme(
  primaryColor: Color(0xFF6366F1),
  secondaryColor: Color(0xFF818CF8),
  backgroundColor: Colors.white,
  textColor: Colors.black87,
  fontFamily: 'Roboto',
  fontSize: 14,
  borderRadius: 12,
)
```

## Building and Running the Example App

### Prerequisites

- [Flutter SDK](https://docs.flutter.dev/get-started/install) (>= 3.10.0)
- Chrome browser (for web) or macOS (for desktop)

### Steps

1. **Install dependencies:**

   ```bash
   cd genassist/plugins/flutter/example
   flutter pub get
   ```

2. **Run on Chrome (web):**

   ```bash
   flutter run -d chrome
   ```

3. **Run on macOS (desktop):**

   ```bash
   flutter run -d macos
   ```

### Running from VSCode

1. Open the `genassist/plugins/flutter/example` folder in VSCode.
2. Install the [Flutter extension](https://marketplace.visualstudio.com/items?itemName=Dart-Code.flutter) if not already installed.
3. Open `lib/main.dart`.
4. Select a target device from the status bar at the bottom (Chrome or macOS).
5. Press **F5** or click **Run > Start Debugging**.

The example app lets you switch between embedded, floating, and fullscreen modes via the menu icon in the app bar.

### Build for Production (Web)

```bash
cd genassist/plugins/flutter/example
flutter build web
```

Output will be in `build/web/`.

## Project Structure

```
lib/
├── gen_agent_chat.dart          # Public API exports
└── src/
    ├── models/                  # Data models (ChatMessage, ChatConfig, etc.)
    ├── services/                # HTTP client, WebSocket, storage, audio
    ├── state/                   # ChatState (ChangeNotifier)
    ├── utils/                   # i18n, time formatting, content parsing
    ├── l10n/                    # Translation files (en, es, fr, de, it, pt)
    └── widgets/                 # All UI widgets
```
