import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getAgentConfig, getAgentIntegrationKey } from "@/services/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/tabs";
import { getApiUrl } from "@/config/api";

import AceEditor from "react-ace";
import "ace-builds/src-noconflict/mode-javascript";
import "ace-builds/src-noconflict/theme-tomorrow_night";
import { Button } from "@/components/button";
import { ChevronLeft, Copy } from "lucide-react";

interface IntegrationConfig {
  url: string;
  name?: string;
}

const SAMPLE_METADATA = {
  id: "cust_123",
  name: "Jane Doe",
  email: "jane.doe@example.com",
};

const IntegrationCodePage: React.FC = () => {
  const { agentId } = useParams<{ agentId: string }>();
  const [config, setConfig] = useState<IntegrationConfig | null>(null);
  const [baseUrl, setBaseUrl] = useState<string>("");
  const [apiKey, setApiKey] = useState<string>("");
  const [copiedSection, setCopiedSection] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!agentId) return;
    (async () => {
      try {
        const c = await getAgentConfig(agentId);
        setConfig({ url: (c.url as string) || "", name: c.name });

        const fetchedBaseUrl = await getApiUrl();
        setBaseUrl(fetchedBaseUrl);

        try {
          const fetchedApiKey = await getAgentIntegrationKey(agentId);
          setApiKey(fetchedApiKey);
        } catch (keyError) {
          setApiKey("your-api-key-here");
        }
      } catch (error) {
        // ignore
      }
    })();
  }, [agentId]);

  if (!config || !baseUrl) {
    return (
      <div className="flex h-[300px] items-center justify-center">
        <p className="text-muted-foreground text-sm">
          Loading integration info…
        </p>
      </div>
    );
  }

  const { url } = config;

  const copyToClipboard = (code: string, sectionId: string) => {
    navigator.clipboard.writeText(code);
    setCopiedSection(sectionId);
    
    // Reset the copied state after 7 seconds
    setTimeout(() => {
      setCopiedSection(null);
    }, 7000);
  };

  return (
    <div className="flex-1 p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex justify-between items-center">
          <div className="flex item-center">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/ai-agents")}
              className="mr-2"
            >
              <ChevronLeft className="h-5 w-5" />
            </Button>
            <h1 className="text-3xl font-bold">Integration Code</h1>
          </div>
          <p className="text-muted-foreground mt-1">
            <span className="font-mono bg-muted px-2 py-0.5 rounded">
              {config.name || agentId?.slice(0, 8)}
            </span>
          </p>
        </div>

        <Tabs defaultValue="react" className="w-full">
          <TabsList className="mb-4">
            <TabsTrigger value="react">React</TabsTrigger>
            <TabsTrigger value="flutter">Flutter</TabsTrigger>
            <TabsTrigger value="swift">iOS (Swift)</TabsTrigger>
          </TabsList>

          {/* React */}
          <TabsContent value="react" className="space-y-4">
            <div>
              <div className="flex justify-between items-center mb-1">
                <h2 className="font-semibold text-lg">1. Install</h2>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => copyToClipboard(`npm install genassist-chat-react\n# or\nyarn add genassist-chat-react`, 'react-install')}
                  className={`flex items-center gap-2 ${copiedSection === 'react-install' ? 'text-muted-foreground' : ''}`}
                >
                  <Copy className="h-4 w-4" />
                  {copiedSection === 'react-install' ? 'Copied!' : 'Copy'}
                </Button>
              </div>
              <AceEditor
                mode="javascript"
                theme="tomorrow_night"
                value={`npm install genassist-chat-react\n# or\nyarn add genassist-chat-react`}
                readOnly
                width="100%"
                height="80px"
                className="integration-code"
                fontSize={14}
                showPrintMargin={false}
                showGutter={false}
                highlightActiveLine={false}
                setOptions={{ useWorker: false }}
              />
            </div>

            <div className="pt-4">
              <div className="flex justify-between items-center mb-1">
                <h2 className="font-semibold text-lg">2. Usage</h2>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => copyToClipboard(`import React from 'react';
import { GenAgentChat } from 'genassist-chat-react';

<GenAgentChat
  baseUrl={process.env.REACT_APP_CHAT_API_URL}
  apiKey={process.env.REACT_APP_CHAT_API_KEY}
  headerTitle="Name"
  placeholder="Ask us anything about your operations..."
  mode="floating"
  theme={{
    primaryColor: '#2962FF',
    backgroundColor: '#ffffff',
    textColor: '#000000',
    fontFamily: 'Roboto, Arial, sans-serif',
    fontSize: '14px'
  }}
/>`, 'react-usage')}
                  className={`flex items-center gap-2 ${copiedSection === 'react-usage' ? 'text-muted-foreground' : ''}`}
                >
                  <Copy className="h-4 w-4" />
                  {copiedSection === 'react-usage' ? 'Copied!' : 'Copy'}
                </Button>
              </div>
              <AceEditor
                mode="javascript"
                theme="tomorrow_night"
                height="450px"
                className="integration-code-usage"
                value={`import React from 'react';
import { GenAgentChat } from 'genassist-chat-react';

<GenAgentChat
  baseUrl={process.env.REACT_APP_CHAT_API_URL}
  apiKey={process.env.REACT_APP_CHAT_API_KEY}
  headerTitle="Name"
  placeholder="Ask us anything about your operations..."
  mode="floating"
  theme={{
    primaryColor: '#2962FF',
    backgroundColor: '#ffffff',
    textColor: '#000000',
    fontFamily: 'Roboto, Arial, sans-serif',
    fontSize: '14px'
  }}
/>`}
                readOnly
                width="100%"
                fontSize={14}
                showPrintMargin={false}
                showGutter
                highlightActiveLine={false}
                setOptions={{ useWorker: false }}
              />
            </div>

            <div className="pt-4">
              <div className="flex justify-between items-center mb-1">
                <h2 className="font-semibold text-lg">3. Environment Setup (.env)</h2>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => copyToClipboard(`REACT_APP_CHAT_API_URL=${baseUrl} # change this to your backend url
REACT_APP_CHAT_API_KEY=${apiKey}`, 'react-env')}
                  className={`flex items-center gap-2 ${copiedSection === 'react-env' ? 'text-muted-foreground' : ''}`}
                >
                  <Copy className="h-4 w-4" />
                  {copiedSection === 'react-env' ? 'Copied!' : 'Copy'}
                </Button>
              </div>
              <AceEditor
                mode="javascript"
                theme="tomorrow_night"
                height="120px"
                className="integration-code-usage"
                value={`REACT_APP_CHAT_API_URL=${baseUrl} # change this to your backend url
REACT_APP_CHAT_API_KEY=${apiKey}`}
                readOnly
                width="100%"
                fontSize={14}
                showPrintMargin={false}
                showGutter
                highlightActiveLine={false}
                setOptions={{ useWorker: false }}
              />
            </div>
          </TabsContent>

          {/* Flutter */}
          <TabsContent value="flutter" className="space-y-4">
            <div>
              <div className="flex justify-between items-center mb-1">
                <h2 className="font-semibold text-lg">
                  1. Add to pubspec.yaml
                </h2>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => copyToClipboard(`dependencies:\n  gen_agent_chat: ^1.0.0`, 'flutter-deps')}
                  className={`flex items-center gap-2 ${copiedSection === 'flutter-deps' ? 'text-muted-foreground' : ''}`}
                >
                  <Copy className="h-4 w-4" />
                  {copiedSection === 'flutter-deps' ? 'Copied!' : 'Copy'}
                </Button>
              </div>
              <AceEditor
                mode="javascript"
                theme="tomorrow_night"
                value={`dependencies:\n  gen_agent_chat: ^1.0.0`}
                readOnly
                width="100%"
                height="80px"
                className="integration-code"
                fontSize={14}
                showPrintMargin={false}
                showGutter={false}
                highlightActiveLine={false}
                setOptions={{ useWorker: false }}
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-1">
                <h2 className="font-semibold text-lg">2. Usage</h2>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => copyToClipboard(`import 'package:gen_agent_chat/gen_agent_chat.dart';

void main() => runApp(MyApp());

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return GenAgentChat(
      url: '${baseUrl}',
      apiKey='Enter your API key here',
      metadata: {
      'id': '${SAMPLE_METADATA.id}',
      'name': '${SAMPLE_METADATA.name}',
      'email': '${SAMPLE_METADATA.email}',
    },
   );
 }
}`, 'flutter-usage')}
                  className={`flex items-center gap-2 ${copiedSection === 'flutter-usage' ? 'text-muted-foreground' : ''}`}
                >
                  <Copy className="h-4 w-4" />
                  {copiedSection === 'flutter-usage' ? 'Copied!' : 'Copy'}
                </Button>
              </div>
              <AceEditor
                mode="javascript"
                theme="tomorrow_night"
                value={`import 'package:gen_agent_chat/gen_agent_chat.dart';

void main() => runApp(MyApp());

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return GenAgentChat(
      url: '${baseUrl}',
      apiKey='Enter your API key here',
      metadata: {
      'id': '${SAMPLE_METADATA.id}',
      'name': '${SAMPLE_METADATA.name}',
      'email': '${SAMPLE_METADATA.email}',
    },
   );
 }
}`}
                readOnly
                width="100%"
                height="370px"
                className="integration-code-usage"
                fontSize={14}
                showPrintMargin={false}
                showGutter
                highlightActiveLine={false}
                setOptions={{ useWorker: false }}
              />
            </div>
          </TabsContent>

          {/* Swift */}
          <TabsContent value="swift" className="space-y-4">
            <div>
              <div className="flex justify-between items-center mb-1">
                <h2 className="font-semibold text-lg">
                  1. Add via Swift Package Manager
                </h2>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => copyToClipboard(`https://dev.azure.com/Ritech/GenAssist/_git/plugin-react`, 'swift-package')}
                  className={`flex items-center gap-2 ${copiedSection === 'swift-package' ? 'text-muted-foreground' : ''}`}
                >
                  <Copy className="h-4 w-4" />
                  {copiedSection === 'swift-package' ? 'Copied!' : 'Copy'}
                </Button>
              </div>
              <AceEditor
                mode="javascript"
                theme="tomorrow_night"
                value={`https://dev.azure.com/Ritech/GenAssist/_git/plugin-react`}
                readOnly
                width="100%"
                height="80px"
                className="integration-code"
                fontSize={14}
                showPrintMargin={false}
                showGutter={false}
                highlightActiveLine={false}
                setOptions={{ useWorker: false }}
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-1">
                <h2 className="font-semibold text-lg">2. Usage</h2>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => copyToClipboard(`import GenAgentChat
struct ContentView: View {
  var body: some View {
    GenAgentChatView(
      url: URL(string: "${baseUrl}")!,
      apiKey="Enter your API key here",
      metadata: [
        "id": "${SAMPLE_METADATA.id}",
        "name": "${SAMPLE_METADATA.name}",
        "email": "${SAMPLE_METADATA.email}"
      ]
    )
  }
}`, 'swift-usage')}
                  className={`flex items-center gap-2 ${copiedSection === 'swift-usage' ? 'text-muted-foreground' : ''}`}
                >
                  <Copy className="h-4 w-4" />
                  {copiedSection === 'swift-usage' ? 'Copied!' : 'Copy'}
                </Button>
              </div>
              <AceEditor
                mode="javascript"
                theme="tomorrow_night"
                value={`import GenAgentChat
struct ContentView: View {
  var body: some View {
    GenAgentChatView(
      url: URL(string: "${baseUrl}")!,
      apiKey="Enter your API key here",
      metadata: [
        "id": "${SAMPLE_METADATA.id}",
        "name": "${SAMPLE_METADATA.name}",
        "email": "${SAMPLE_METADATA.email}"
      ]
    )
  }
}`}
                readOnly
                width="100%"
                height="320px"
                className="integration-code-usage"
                fontSize={14}
                showPrintMargin={false}
                showGutter
                highlightActiveLine={false}
                setOptions={{ useWorker: false }}
              />
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default IntegrationCodePage;
