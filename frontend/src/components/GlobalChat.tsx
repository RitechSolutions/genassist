import { GenAgentChat } from "genassist-chat-react";
import { useEffect, useState } from "react";
import { getApiUrl } from "@/config/api";
import { isWsEnabled } from "@/config/api";

export const GlobalChat = () => {
  const [baseUrl, setBaseUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const genassistApiKey = import.meta.env.VITE_GENASSIST_CHAT_APIKEY;  

  useEffect(() => {
    (async () => {
      try {
        const apiUrl = await getApiUrl();
        const baseUrl = new URL("..", apiUrl).toString();
        setBaseUrl(baseUrl);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to initialize chat";
        setError(message);
      }
    })();
  }, []);

  if (error || !baseUrl) {
    return null;
  }

  return (
    <GenAgentChat
      baseUrl={baseUrl}
      apiKey={genassistApiKey}
      tenant={'dyrkaj'}
      headerTitle="Genassist Chat"
      placeholder="Ask anything..."
      theme={{
        primaryColor: "#4F46E5",
        backgroundColor: "#ffffff",
        textColor: "#000000",
        fontFamily: "Roboto, Arial, sans-serif",
        fontSize: "14px",
      }}
      useWs={isWsEnabled}
      mode="floating"
      floatingConfig={{
        position: "bottom-right",
      }}
      useFile={true}
    />
  );
};