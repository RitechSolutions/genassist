import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  GenAgentChat,
  GenAgentConfigPanel,
  type ChatSettingsConfig,
  type ChatTheme,
} from "genassist-chat-react";
import { getAgentIntegrationKey } from "@/services/api";
import { getApiUrl, isWsEnabled } from "@/config/api";
import { Button } from "@/components/button";
import { ArrowLeft } from "lucide-react";
import IntegrationCodePanel from "@/views/AIAgents/components/Customer/IntegrationCodePanel";

export default function ChatAsCustomer() {
  const { agentId } = useParams<{ agentId: string }>();
  const tenant = localStorage.getItem("tenant_id");
  const navigate = useNavigate();

  const [baseUrl, setBaseUrl] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<ChatTheme>({
    primaryColor: "#4F46E5",
    secondaryColor: "#f5f5f5",
    backgroundColor: "#ffffff",
    textColor: "#000000",
    fontFamily: "Inter, sans-serif",
    fontSize: "15px",
  });
  const [chatSettings, setChatSettings] = useState<ChatSettingsConfig>({
    name: "Genassist",
    description: "Support",
  });
  const [metadata, setMetadata] = useState<Record<string, any>>({});

  useEffect(() => {
    if (!agentId) {
      setError("No agent specified");
      return;
    }

    (async () => {
      try {
        const apiUrl = await getApiUrl();
        const baseUrl = new URL("..", apiUrl).toString();
        setBaseUrl(baseUrl);

        const key = await getAgentIntegrationKey(agentId);
        setApiKey(key);
      } catch (err: any) {
        setError(err.message || "Failed to initialize chat");
        setTimeout(() => navigate("/ai-agents"), 2000);
      }
    })();
  }, [agentId, navigate]);

  if (error) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-4 text-center">
        <p className="mb-2 text-red-600">{error}</p>
        <p>Redirecting back…</p>
      </div>
    );
  }

  if (!baseUrl || !apiKey) {
    return (
      <div className="h-full flex items-center justify-center">
        <p>Loading chat…</p>
      </div>
    );
  }

  return (
    <div className="h-full min-h-0 w-full">
      <div className="h-full min-h-0 w-full grid grid-cols-1 lg:grid-cols-[360px_minmax(0,1fr)_360px] gap-6 p-6">
        <div className="min-h-0 flex w-full flex-col items-start gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/ai-agents")}
            className="rounded-full bg-white shadow-lg"
            aria-label="Back to AI Agents"
          >
            <ArrowLeft />
          </Button>
          <GenAgentConfigPanel
            theme={theme}
            onThemeChange={setTheme}
            chatSettings={chatSettings}
            onChatSettingsChange={setChatSettings}
            metadata={metadata}
            onMetadataChange={setMetadata}
            defaultOpen={{ appearance: true, settings: false, metadata: false }}
            style={{
              width: "100%",
              maxWidth: "100%",
              flex: "0 1 auto",
              maxHeight: "calc(100vh - 50px)",
              overflowY: "auto",
            }}
            onSave={({ theme, chatSettings, metadata }) => {
              setTheme(theme);
              setChatSettings(chatSettings);
              setMetadata(metadata);
            }}
          />
        </div>

        <div className="min-h-0 flex h-full items-center justify-center">
          <GenAgentChat
            baseUrl={baseUrl}
            apiKey={apiKey}
            tenant={tenant ?? undefined}
            metadata={metadata}
            theme={theme}
            headerTitle="Chat as Customer"
            placeholder="Ask a question..."
            useWs={isWsEnabled}
            onError={(error) => {
              // ignore
            }}
          />
        </div>

        <div className="min-h-0 flex h-full w-full">
          <IntegrationCodePanel
            agentId={agentId}
            className="w-full h-full overflow-y-auto"
            style={{ maxHeight: "calc(100vh - 50px)" }}
          />
        </div>
      </div>
    </div>
  );
}
