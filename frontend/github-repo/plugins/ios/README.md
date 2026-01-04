# GenassistChatIOS

A SwiftUI chat interface with speech-to-text and text-to-speech capabilities for iOS applications.

## Requirements

- iOS 15.0+
- Xcode 13.0+
- Swift 6.0+

## Installation

### Swift Package Manager

Add the following to your `Package.swift` file:

```swift
dependencies: [
    .package(url: "YOUR_PACKAGE_URL", from: "1.0.0")
]
```

## Required Permissions

To use the speech-to-text functionality, you need to add the following keys to your app's Info.plist file:

```xml
<key>NSMicrophoneUsageDescription</key>
<string>We need access to your microphone to enable speech-to-text functionality.</string>

<key>NSSpeechRecognitionUsageDescription</key>
<string>We need speech recognition to convert your voice to text.</string>
```

**Note**: Permissions are only requested when the user actually presses the microphone button, not when the chat interface is initialized. This provides a better user experience by avoiding unnecessary permission requests.

## Usage

### Basic Usage

```swift
import GenassistChatIOS

struct ContentView: View {
    var body: some View {
        GenassistChat(
            baseURL: "YOUR_API_URL",
            apiKey: "YOUR_API_KEY",
            metadata: ChatMetadata()
        )
    }
}
```

### Advanced Configuration with Voice Features

```swift
import GenassistChatIOS

struct ContentView: View {
    var body: some View {
        GenassistChat(
            baseURL: "YOUR_API_URL",
            apiKey: "YOUR_API_KEY",
            metadata: ChatMetadata(),
            configuration: ChatConfiguration(
                useVoice: true,                    // Enable voice input/output
                enableTextToSpeech: true,          // Enable text-to-speech responses
                speechRate: AVSpeechUtteranceDefaultSpeechRate,
                speechVolume: 0.8
            )
        )
    }
}
```

## Features

- Real-time chat interface
- Speech-to-text functionality (configurable)
- Text-to-speech responses (when messages are sent via speech)
- Audio feedback for recording start/stop
- Visual indicators for speech-to-text and text-to-speech
- Customizable UI and speech settings
- Support for multiple languages
- Error handling and state management
- Voice functionality can be completely disabled for text-only chat

## Text-to-Speech Logic

The chat interface includes intelligent text-to-speech functionality:

1. **Speech-to-Text**: Users can long-press the microphone button to record their message
2. **Automatic Response**: When a message is sent via speech-to-text, the agent's response is automatically read aloud
3. **Visual Indicators**: Messages sent via speech show a "Voice" indicator
4. **Controls**: Users can stop text-to-speech playback via the menu

## Permission Handling

The chat interface handles voice permissions intelligently:

1. **Lazy Permission Requests**: Permissions are only requested when the user actually tries to use voice functionality
2. **Visual Feedback**: The microphone button shows different states based on permission status:
   - `mic`: Voice enabled and permissions granted
   - `mic.slash`: Voice enabled but permissions not granted
   - `arrow.up`: Text input mode
3. **Permission Alerts**: If permissions are denied, users can tap to open Settings
4. **Automatic Refresh**: Permissions are automatically checked when returning from Settings

## Configuration Options

### ChatConfiguration

- `useVoice`: Enable/disable all voice functionality including speech-to-text and text-to-speech (default: true)
- `enableTextToSpeech`: Enable/disable text-to-speech functionality (default: true)
- `speechRate`: Speed of speech playback (default: AVSpeechUtteranceDefaultSpeechRate)
- `speechVolume`: Volume of speech playback (default: 0.8)

### Voice Control Examples

```swift
// Text-only chat (no voice features)
ChatConfiguration(useVoice: false)

// Voice input only (no text-to-speech)
ChatConfiguration(useVoice: true, enableTextToSpeech: false)

// Full voice features enabled
ChatConfiguration(useVoice: true, enableTextToSpeech: true)
```

## License

[Your License] 