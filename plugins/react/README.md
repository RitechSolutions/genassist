# GenAssist Chat React

A reusable React chat component for integrating with GenAssist API.

## Installation

```bash
npm install genassist-chat-react
```

## Usage

### Basic Usage

```jsx
import React from 'react';
import { GenAgentChat } from 'genassist-chat-react';

function App() {
  return (
    <div style={{ height: '600px', width: '400px' }}>
      <GenAgentChat 
        baseUrl="https://your-api-base-url.com" 
        apiKey="your-api-key"
        tenant="your-tenant-id"
      />
    </div>
  );
}

export default App;
```

### With Custom Theme and User Data

```jsx
import React from 'react';
import { GenAgentChat } from 'genassist-chat-react';

function App() {
  const userData = {
    userId: '12345',
    username: 'johndoe',
    email: 'john@example.com',
    // Any additional metadata
  };

  const theme = {
    primaryColor: '#4a90e2',
    secondaryColor: '#f5f5f5',
    backgroundColor: '#ffffff',
    textColor: '#333333',
    fontFamily: 'Roboto, sans-serif',
    fontSize: '15px',
  };

  return (
    <div style={{ height: '600px', width: '400px' }}>
      <GenAgentChat 
        baseUrl="https://your-api-base-url.com" 
        apiKey="your-api-key"
        tenant="your-tenant-id"
        userData={userData}
        theme={theme}
        useWS={true}
        reCaptchaKey={your-recaptcha-site-key}
        headerTitle="Customer Support"
        placeholder="Ask a question..."
        onError={() => {}}
        onTakeover={handleTakeover}
        noColorAnimation={false}
        useFile={false}
        useAudio={false}
        allowedExtensions={['image/*']}
      />
    </div>
  );
}

export default App;
```

## Props

| Prop | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| baseUrl | string | Yes | - | Base URL for the API endpoints |
| apiKey | string | Yes | - | API key for authentication |
| userData | object | No | - | Any user metadata to include |
| onError | function | No | - | Error handler callback |
| onTakeover | function | No | - | Callback triggered when a takeover event occurs |
| theme | object | No | - | Custom theme options |
| headerTitle | string | No | 'Chat' | Title displayed in the chat header |
| placeholder | string | No | 'Type a message...' | Placeholder text for the input |
| useWS | boolean | false | true | 'Enable or disable websocket...' |
| useAudio | boolean | false | false | 'Enable or disable audio on chat input...' |
| useFile | boolean | false | false | 'Enable or disable file attachments on chat input...' |
| reCaptchaKey | string | false | undefined | 'Use google reCaptchaV3 site-key...' |
| allowedExtensions | string[] | false | undefined | 'Look for type AllowedExtension and see the supported list of extensions' |



## Theme Options

| Option | Type | Description |
|--------|------|-------------|
| primaryColor | string | Primary color for buttons and user messages |
| secondaryColor | string | Background color for agent messages |
| backgroundColor | string | Background color for the chat container |
| textColor | string | Text color for agent messages |
| fontFamily | string | Font family for all text |
| fontSize | string | Font size for messages |

## API Endpoints

The component interacts with the following endpoints:

1. Start Conversation: `POST /api/conversations/in-progress/start`
2. Update Conversation: `POST /api/conversations/in-progress/update/{conversation_id}`
3. WebSocket: `/api/conversations/ws/{conversation_id}?access_token={token}&lang=en&topics=message&topics=takeover`

## Run
./
yarn run build

cd example-app

yarn run dev