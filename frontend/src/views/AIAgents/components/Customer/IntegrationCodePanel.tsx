import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { useParams } from "react-router-dom";
import { Copy } from "lucide-react";
import { getAgentConfig, getAgentIntegrationKey } from "@/services/api";
import { getApiUrl } from "@/config/api";
import { getTenantId } from "@/services/auth";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/tabs";
import { cn } from "@/helpers/utils";

interface IntegrationCodePanelProps {
  agentId?: string;
  className?: string;
  style?: CSSProperties;
}

interface CodeSectionProps {
  title: string;
  code: string;
  copyId: string;
  copiedSection: string | null;
  onCopy: (code: string, sectionId: string) => void;
  minHeightClass?: string;
}

const SAMPLE_METADATA = {
  id: "cust_123",
  name: "Jane Doe",
  email: "jane.doe@example.com",
};

const CodeSection = ({
  title,
  code,
  copyId,
  copiedSection,
  onCopy,
  minHeightClass,
}: CodeSectionProps) => {
  const isCopied = copiedSection === copyId;

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      <div
        className={cn(
          "relative rounded-xl border border-[#E5E7EB] bg-[#F7F7F8] p-4",
          minHeightClass
        )}
      >
        <button
          type="button"
          onClick={() => onCopy(code, copyId)}
          className="absolute right-3 top-3 inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-gray-500 hover:bg-white/70 hover:text-gray-900"
          aria-label={`Copy ${title}`}
        >
          <Copy className="h-4 w-4" />
          {isCopied ? "Copied" : "Copy"}
        </button>
        <pre className="whitespace-pre-wrap break-words pr-12 text-xs leading-relaxed text-gray-700 font-mono">
          {code}
        </pre>
      </div>
    </div>
  );
};

export const IntegrationCodePanel = ({
  agentId: agentIdProp,
  className,
  style,
}: IntegrationCodePanelProps) => {
  const { agentId: agentIdParam } = useParams<{ agentId: string }>();
  const agentId = agentIdProp ?? agentIdParam;
  const [configName, setConfigName] = useState<string | null>(null);
  const [baseUrl, setBaseUrl] = useState<string>("");
  const [apiKey, setApiKey] = useState<string>("");
  const [copiedSection, setCopiedSection] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);

  useEffect(() => {
    if (!agentId) return;
    setBaseUrl("");
    setApiKey("");
    setConfigName(null);
    setTenantId(getTenantId());

    (async () => {
      try {
        const c = await getAgentConfig(agentId);
        setConfigName(c.name ?? null);

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

  const copyToClipboard = (code: string, sectionId: string) => {
    navigator.clipboard.writeText(code);
    setCopiedSection(sectionId);

    setTimeout(() => {
      setCopiedSection(null);
    }, 7000);
  };

  const panelLabel = configName || (agentId ? agentId.slice(0, 8) : undefined);

  if (!baseUrl) {
    return (
      <div
        className={cn(
          "w-full rounded-2xl border border-[#E5E7EB] bg-white p-4 text-sm text-muted-foreground shadow-sm",
          className
        )}
        style={style}
      >
        Loading integration info...
      </div>
    );
  }

  const curlWorkflowExecute = `curl -X 'POST' \\
  '${baseUrl}genagent/agents/${
    agentId || "019b8614-72d2-74bd-8b48-8388ba371d40"
  }/query/${apiKey}' \\
  -H 'accept: application/json' \\
  -H 'Content-Type: application/json' \\
  -H "X-API-Key: ${apiKey}"${
    tenantId
      ? ` \\
  -H "x-tenant-id: ${tenantId}"`
      : ""
  } \\
  -d '{
  "query": "string",
  "metadata": {

  }
}'
`;
  const curlCallInitiation = `curl -X POST \\
    "${baseUrl}conversations/in-progress/start" \\
    -H "Accept: application/json" \\
    -H "Content-Type: application/json" \\
    -H "X-API-Key: ${apiKey}"${
    tenantId
      ? ` \\
    -H "x-tenant-id: ${tenantId}"`
      : ""
  } \\
    -d '{
    "messages": [],
    "recorded_at": "2025-12-22T11:28:22.293Z",
    "data_source_id": "00000000-0000-0000-0000-000000000000",
    "metadata": {}
  }'
`;
  const curlCallUpdate = `curl -X PATCH \\
    "${baseUrl}conversations/in-progress/update/019b4a41-fc2d-776e-96f5-d6ea3cbe7776" \\
    -H "Accept: application/json" \\
    -H "Content-Type: application/json" \\
    -H "X-API-Key: ${apiKey}"${
    tenantId
      ? ` \\
    -H "x-tenant-id: ${tenantId}"`
      : ""
  } \\
    -d '{
    "messages": [
      {
        "create_time": "2025-12-22T11:09:22.762Z",
        "start_time": 0,
        "end_time": 0,
        "speaker": "user",
        "text": "Your message here",
        "type": "message"
      }
    ],
    "metadata": {},
    "llm_analyst_id": null
  }'
`;

  const reactInstall = `npm install genassist-chat-react
# or
yarn add genassist-chat-react`;
  const reactUsage = `import React from 'react';
import { GenAgentChat } from 'genassist-chat-react';

<GenAgentChat
  baseUrl={process.env.REACT_APP_CHAT_API_URL}
  apiKey={process.env.REACT_APP_CHAT_API_KEY}
  headerTitle="Name"
  agentName="Agent"
  logoUrl="https://example.com/logo.png"
  placeholder="Ask us anything..."
  tenant={process.env.REACT_APP_TENANT_ID || undefined}
  mode="floating"
  useWs={true}
  theme={{
    primaryColor: '#2962FF',
    backgroundColor: '#ffffff',
    textColor: '#000000',
    fontFamily: 'Roboto, Arial, sans-serif',
    fontSize: '14px'
  }}
/>`;
  const reactEnv = `REACT_APP_CHAT_API_URL=${baseUrl} # change this to your backend url
REACT_APP_CHAT_API_KEY=${apiKey}
REACT_APP_TENANT_ID=your-tenant-id # optional, if applicable`;

  const flutterDeps = `dependencies:
  gen_agent_chat: ^1.0.0`;
  const flutterUsage = `import 'package:gen_agent_chat/gen_agent_chat.dart';

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
}`;

  const swiftPackage = `https://dev.azure.com/Ritech/GenAssist/_git/plugin-react`;
  const swiftUsage = `import GenAgentChat
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
}`;

  return (
    <div
      className={cn(
        "w-full rounded-2xl border border-[#E5E7EB] bg-white shadow-sm",
        className
      )}
      style={style}
      title={panelLabel}
    >
      <Tabs defaultValue="curl" className="w-full">
        <div className="sticky top-0 z-10 rounded-t-2xl bg-white px-4 pt-4 pb-3">
          <TabsList className="grid w-full grid-cols-4 rounded-xl bg-[#F4F4F5] p-1">
            <TabsTrigger
              value="curl"
              className="rounded-lg text-xs font-medium data-[state=active]:bg-white data-[state=active]:text-gray-900 data-[state=active]:shadow-sm"
            >
              Curl -X
            </TabsTrigger>
            <TabsTrigger
              value="react"
              className="rounded-lg text-xs font-medium data-[state=active]:bg-white data-[state=active]:text-gray-900 data-[state=active]:shadow-sm"
            >
              React
            </TabsTrigger>
            <TabsTrigger
              value="flutter"
              className="rounded-lg text-xs font-medium data-[state=active]:bg-white data-[state=active]:text-gray-900 data-[state=active]:shadow-sm"
            >
              Flutter
            </TabsTrigger>
            <TabsTrigger
              value="swift"
              className="rounded-lg text-xs font-medium data-[state=active]:bg-white data-[state=active]:text-gray-900 data-[state=active]:shadow-sm"
            >
              iOS (Swift)
            </TabsTrigger>
          </TabsList>
        </div>

        <div className="px-4 pb-4">
          <TabsContent value="curl" className="mt-4 space-y-6">
            <CodeSection
              title="1. Start Conversation"
              code={curlCallInitiation}
              copyId="start-conversation"
              copiedSection={copiedSection}
              onCopy={copyToClipboard}
              minHeightClass="min-h-[120px]"
            />
            <CodeSection
              title="2. Update Conversation"
              code={curlCallUpdate}
              copyId="update-conversation"
              copiedSection={copiedSection}
              onCopy={copyToClipboard}
              minHeightClass="min-h-[240px]"
            />

            <CodeSection
              title="1. Direct Agent Execution"
              code={curlWorkflowExecute}
              copyId="direct-agent-execution"
              copiedSection={copiedSection}
              onCopy={copyToClipboard}
              minHeightClass="min-h-[120px]"
            />
          </TabsContent>

          <TabsContent value="react" className="mt-4 space-y-6">
            <CodeSection
              title="1. Install"
              code={reactInstall}
              copyId="react-install"
              copiedSection={copiedSection}
              onCopy={copyToClipboard}
              minHeightClass="min-h-[120px]"
            />
            <CodeSection
              title="2. Usage"
              code={reactUsage}
              copyId="react-usage"
              copiedSection={copiedSection}
              onCopy={copyToClipboard}
              minHeightClass="min-h-[240px]"
            />
            <CodeSection
              title="3. Environment Setup (.env)"
              code={reactEnv}
              copyId="react-env"
              copiedSection={copiedSection}
              onCopy={copyToClipboard}
              minHeightClass="min-h-[120px]"
            />
          </TabsContent>

          <TabsContent value="flutter" className="mt-4 space-y-6">
            <CodeSection
              title="1. Add to pubspec.yaml"
              code={flutterDeps}
              copyId="flutter-deps"
              copiedSection={copiedSection}
              onCopy={copyToClipboard}
              minHeightClass="min-h-[120px]"
            />
            <CodeSection
              title="2. Usage"
              code={flutterUsage}
              copyId="flutter-usage"
              copiedSection={copiedSection}
              onCopy={copyToClipboard}
              minHeightClass="min-h-[240px]"
            />
            <CodeSection
              title="3. Environment Setup (.env)"
              code={reactEnv}
              copyId="flutter-env"
              copiedSection={copiedSection}
              onCopy={copyToClipboard}
              minHeightClass="min-h-[120px]"
            />
          </TabsContent>

          <TabsContent value="swift" className="mt-4 space-y-6">
            <CodeSection
              title="1. Add via Swift Package Manager"
              code={swiftPackage}
              copyId="swift-package"
              copiedSection={copiedSection}
              onCopy={copyToClipboard}
              minHeightClass="min-h-[120px]"
            />
            <CodeSection
              title="2. Usage"
              code={swiftUsage}
              copyId="swift-usage"
              copiedSection={copiedSection}
              onCopy={copyToClipboard}
              minHeightClass="min-h-[240px]"
            />
            <CodeSection
              title="3. Environment Setup (.env)"
              code={reactEnv}
              copyId="swift-env"
              copiedSection={copiedSection}
              onCopy={copyToClipboard}
              minHeightClass="min-h-[120px]"
            />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
};

export default IntegrationCodePanel;
