import { GenAgentChat } from "genassist-chat-react";
import { useEffect, useState } from "react";
import { getApiUrl, getWsUrl } from "@/config/api";
import { isWsEnabled, isPollEnabled } from "@/config/api";

export const GlobalChat = () => {
  const [baseUrl, setBaseUrl] = useState<string | null>(null);
  const [websocketUrl, setWebsocketUrl] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const genassistApiKey = import.meta.env.VITE_GENASSIST_CHAT_APIKEY;
  // const tenantId = localStorage.getItem('tenant_id') as string | undefined;

  useEffect(() => {
    (async () => {
      try {
        const apiUrl = await getApiUrl();
        const baseUrl = new URL("..", apiUrl).toString();
        setBaseUrl(baseUrl);

        const websocketUrl = await getWsUrl();
        setWebsocketUrl(websocketUrl);
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
      websocketUrl={websocketUrl}
      apiKey={genassistApiKey}
      // tenant={tenantId}
      headerTitle="Genassist Chat"
      brandLogoUrl="https://cdn.prod.website-files.com/689da2a76e017a77b0596d1c/694291f3d893f585af78bdd7_genassist_logo.svg"
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
      quickInput={true}
      usePoll={isPollEnabled}
    />
  );
};