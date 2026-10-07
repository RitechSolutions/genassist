import { GenAgentChat } from "genassist-chat-react";
import { useEffect, useState } from "react";
import { getApiUrl, getWsUrl } from "@/config/api";
import { isWsEnabled, isPollEnabled } from "@/config/api";
import { useChatTheme, useColorMode } from "@/hooks/useChatTheme";

const BRAND_LOGO_URL =
  "https://cdn.prod.website-files.com/689da2a76e017a77b0596d1c/694291f3d893f585af78bdd7_genassist_logo.svg";
const BRAND_LOGO_DARK_URL =
  "https://raw.githubusercontent.com/RitechSolutions/genassist/89b52401ca2367428bfc1df54ebf0051a313dc51/plugins/react/src/assets/logo_dark_mode.png";

export const GlobalChat = () => {
  const [baseUrl, setBaseUrl] = useState<string | null>(null);
  const [websocketUrl, setWebsocketUrl] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const genassistApiKey = import.meta.env.VITE_GENASSIST_CHAT_APIKEY;

  // Follows the app's light/dark mode. Only type is pinned here: primaryColor
  // comes from the palette, which carries the brand blue in light and a
  // lightened variant in dark (the brand blue is unreadable on a dark surface).
  const theme = useChatTheme({
    fontFamily: "Roboto, Arial, sans-serif",
    fontSize: "14px",
  });
  const colorMode = useColorMode();
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
      brandLogoUrl={colorMode === "dark" ? BRAND_LOGO_DARK_URL : BRAND_LOGO_URL}
      theme={theme}
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