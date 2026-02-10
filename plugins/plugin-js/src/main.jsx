import React from "react";
import ReactDOM from "react-dom/client";
import { GenAgentChat } from "genassist-chat-react";

// Import CSS files
import "./font.css";

// Import index.css if you want to override the default styles
// import "./index.css";

// Keep a reference to the React root so we can safely re-bootstrap
let genassistRoot = null;

function bootstrap() {
  const cfg = window.GENASSIST_CONFIG || {};
  const container = document.getElementById("genassist-chat-root");

  if (!container) return;

  if (!genassistRoot) {
    genassistRoot = ReactDOM.createRoot(container);
  }

  genassistRoot.render(
    <GenAgentChat
      baseUrl={cfg.baseUrl}
      apiKey={cfg.apiKey}
      tenant={cfg.tenant ?? undefined}
      headerTitle={cfg.headerTitle ?? "GenAssist"}
      agentName={cfg.agentName ?? "GenAssist"}
      description={cfg.description ?? "Your Virtual Assistant"}
      logoUrl={cfg.logoUrl}
      placeholder={cfg.placeholder ?? "Ask a question"}
      mode={cfg.mode ?? "floating"}
      serverUnavailableMessage={
        cfg.serverUnavailableMessage ??
        "Support is currently offline. Please try again later or contact us."
      }
      noColorAnimation={cfg.noColorAnimation ?? true}
      theme={cfg.theme}
      useWs={cfg.useWs ?? false}
      useFiles={cfg.useFiles ?? false}
    />,
  );
}

// expose for debugging if needed
window.GenassistBootstrap = bootstrap;

// auto-start if config exists
bootstrap();
