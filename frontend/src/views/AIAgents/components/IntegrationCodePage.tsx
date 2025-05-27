import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getAgentConfig } from "@/services/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/tabs";
import { getApiUrl } from "@/config/api";

import AceEditor from "react-ace";
import "ace-builds/src-noconflict/mode-javascript";
import "ace-builds/src-noconflict/theme-tomorrow_night";
import { Button } from "@/components/button";
import { ChevronLeft } from "lucide-react";

interface IntegrationConfig {
  url: string;
  name?: string; 
}

const SAMPLE_CUSTOMER = {
  id: "cust_123",
  name: "Jane Doe",
  email: "jane.doe@example.com",
};

const IntegrationCodePage: React.FC = () => {
  const { agentId } = useParams<{ agentId: string }>();
  const [config, setConfig] = useState<IntegrationConfig | null>(null);
  const [baseUrl, setBaseUrl] = useState<string>(""); 
  const navigate = useNavigate();

  useEffect(() => {
    if (!agentId) return;
    (async () => {
      try {
        const c = await getAgentConfig(agentId);
        setConfig({ url: c.url, name: c.name, });

        const fetchedBaseUrl = await getApiUrl();
        setBaseUrl(fetchedBaseUrl);
      } catch (error) {
        console.error("Failed to fetch agent config:", error);
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
  const apiKeyPlaceholder = "Enter your API key here";
  
  return (
    <div className="mx-auto px-4 space-y-8">
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
            <h2 className="font-semibold text-lg mb-1">1. Install</h2>
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
            <h2 className="font-semibold text-lg mb-1">2. Usage</h2>
            <AceEditor
              mode="javascript"
              theme="tomorrow_night"
              height="450px"
              className="integration-code-usage"
              value={`import React from 'react';
import { GenAgentChat } from 'genassist-chat-react';

function App() {
  const userData = {
    userId: '${SAMPLE_CUSTOMER.id}',
    username: '${SAMPLE_CUSTOMER.name}',
    email: '${SAMPLE_CUSTOMER.email}',
  };

  return (
    <div style={{ height: '600px', width: '400px' }}>
      <GenAgentChat 
        baseUrl="${baseUrl}" 
        apiKey="${apiKeyPlaceholder}"
        userData={userData}
      />
    </div>
  );
}

export default App;`}
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
            <h2 className="font-semibold text-lg mb-1">
              1. Add to pubspec.yaml
            </h2>
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
            <h2 className="font-semibold text-lg mb-1">2. Usage</h2>
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
      apiKey='${apiKeyPlaceholder}',
      customer: {
        'id': '${SAMPLE_CUSTOMER.id}',
        'name': '${SAMPLE_CUSTOMER.name}',
        'email': '${SAMPLE_CUSTOMER.email}',
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
            <h2 className="font-semibold text-lg mb-1">
              1. Add via Swift Package Manager
            </h2>
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
            <h2 className="font-semibold text-lg mb-1">2. Usage</h2>
            <AceEditor
              mode="javascript"
              theme="tomorrow_night"
              value={`import GenAgentChat

struct ContentView: View {
  var body: some View {
    GenAgentChatView(
      url: URL(string: "${baseUrl}")!,
      apiKey="${apiKeyPlaceholder}",
      customer: [
        "id": "${SAMPLE_CUSTOMER.id}",
        "name": "${SAMPLE_CUSTOMER.name}",
        "email": "${SAMPLE_CUSTOMER.email}"
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
  );
};

export default IntegrationCodePage;
