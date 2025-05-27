import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { GenAgentChat } from "genassist-chat-react";
import { getAgentIntegrationKey } from "@/services/api";
import { getApiUrl } from "@/config/api";

export default function ChatAsCustomer() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();

  const [baseUrl, setBaseUrl] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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
        console.error("Chat init error:", err);
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
    <div
      style={{
        height: "600px",
        width: "400px",
        color: "#333",
        margin: "40px auto",
        border: "1px solid #ddd",
        borderRadius: 8,
        overflow: "hidden",
      }}
    >
      <GenAgentChat
        baseUrl={baseUrl}
        apiKey={apiKey}
        userData={{ role: "ai agent" }}
        headerTitle="Chat as Customer"
        placeholder="Ask a question..."
        onError={(error) => {
          console.error("Chat error:", error);
          console.error("Chat error:", error);
        }}
      />
    </div>
  );
}
