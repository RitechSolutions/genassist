import { GenAgentChat } from "genassist-chat-react";
import { useEffect, useState } from "react";
import { getApiUrl, getGenassistChatApiKey, getWebsocketUrl } from "@/config/api";
import { isWsEnabled, isPollEnabled } from "@/config/api";

export const GlobalChat = () => {
  const [baseUrl, setBaseUrl] = useState<string | null>(null);
  const [websocketUrl, setWebsocketUrl] = useState<string | null>(null);
  const [genassistApiKey, setGenassistApiKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

      // get websocket url
      try {
        const websocketUrl = await getWebsocketUrl();
        setWebsocketUrl(websocketUrl);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to initialize chat";
        setError(message);
      }

      // get genassist api key
      try {
        const genassistApiKey = await getGenassistChatApiKey();
        setGenassistApiKey(genassistApiKey);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to initialize chat";
        setError(message);
      }

    })();
  }, [baseUrl, websocketUrl, genassistApiKey]);

  if (error || !baseUrl || !websocketUrl || !genassistApiKey) {
    return null;
  }

  return (
    <GenAgentChat
      baseUrl={baseUrl}
      websocketUrl={websocketUrl}
      apiKey={genassistApiKey}
      tenant={undefined}
      headerTitle="Genassist Chat"
      placeholder="Ask anything..."
      theme={{
        primaryColor: "#173DED",
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
      usePoll={isPollEnabled}
    />
  );
};