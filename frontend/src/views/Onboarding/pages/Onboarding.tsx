import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorBanner } from "@/views/Onboarding/components/ErrorBanner";
import { OnboardingChat } from "@/views/Onboarding/components/OnboardingChat";
import { OnboardingFooter } from "@/views/Onboarding/components/OnboardingFooter";
import { OnboardingHeader } from "@/views/Onboarding/components/OnboardingHeader";
import { OnboardingNameAgent } from "@/views/Onboarding/components/OnboardingNameAgent";
import { useOnboardingChat } from "@/views/Onboarding/hooks/useOnboardingChat";
import { isWorkflowDraft } from "@/views/Onboarding/utils/extractWorkflowDraft";
import { parseInteractiveContentBlocks } from "genassist-chat-react";
import { useRoutesContext } from "@/context/RoutesContext";

type OnboardingScreen = "chat" | "name-agent";

export const WORKFLOW_DRAFT_STORAGE_KEY = "onboarding_workflow_draft";
export const AGENT_NAME_STORAGE_KEY = "onboarding_agent_name";

export default function Onboarding() {
  const { registrationStatus } = useRoutesContext();
  const navigate = useNavigate();
  const {
    prompt,
    setPrompt,
    agentReply,
    messages,
    isThinking,
    liveTurn,
    titleText,
    welcomeFaqs,
    isSending,
    error,
    hasConfig,
    sendMessage,
    answerQuestion,
    reactToMessage,
    workflowDraft,
    isWorkflowReady,
  } = useOnboardingChat({ registrationStatus });

  const [screen, setScreen] = useState<OnboardingScreen>(() => {
    try {
      const savedDraftRaw = localStorage.getItem(WORKFLOW_DRAFT_STORAGE_KEY);
      if (!savedDraftRaw) return "chat";
      const savedDraftParsed = JSON.parse(savedDraftRaw) as unknown;
      return isWorkflowDraft(savedDraftParsed) ? "name-agent" : "chat";
    } catch {
      return "chat";
    }
  });
  const [agentName, setAgentName] = useState(() => {
    try {
      return localStorage.getItem(AGENT_NAME_STORAGE_KEY) || "";
    } catch {
      return "";
    }
  });

  // Answers the builder offered inside its latest reply (interactive content blocks).
  const replyOptions = useMemo(() => {
    if (!agentReply) return [];
    const blocks = parseInteractiveContentBlocks(agentReply);
    const options: string[] = [];
    blocks.forEach((block) => {
      if (block.kind === "options") {
        options.push(...block.options);
      } else if (block.kind === "items") {
        options.push(...block.items.map((item) => item.name));
      }
    });
    return options;
  }, [agentReply]);

  const effectiveScreen: OnboardingScreen = isWorkflowReady ? "name-agent" : screen;

  useEffect(() => {
    if (!isWorkflowReady || !workflowDraft) return;

    try {
      localStorage.setItem(WORKFLOW_DRAFT_STORAGE_KEY, JSON.stringify(workflowDraft));
    } catch {
      // ignore
    }

    if (screen !== "name-agent") {
      setScreen("name-agent");
    }
  }, [isWorkflowReady, workflowDraft, screen]);

  const isInputDisabled = !hasConfig || isSending;

  const handleAgentNameChange = (val: string) => {
    setAgentName(val);
    try {
      localStorage.setItem(AGENT_NAME_STORAGE_KEY, val);
    } catch {
      // ignore
    }
  };

  const handleContinue = () => {
    const trimmedName = agentName.trim();
    if (!trimmedName) return;

    try {
      localStorage.setItem(AGENT_NAME_STORAGE_KEY, trimmedName);
    } catch {
      // ignore
    }

    // Redirect to login — post-login logic will pick up the draft
    navigate("/login", { state: { from: { pathname: "/onboarding" } } });
  };

  // Drop the saved draft and go back to the chat, so an abandoned draft never traps the user here.
  const handleStartOver = () => {
    try {
      localStorage.removeItem(WORKFLOW_DRAFT_STORAGE_KEY);
      localStorage.removeItem(AGENT_NAME_STORAGE_KEY);
    } catch {
      // ignore
    }
    window.location.reload();
  };

  return (
    <div className="relative flex h-screen flex-col overflow-hidden bg-background">
      <OnboardingHeader />

      <main className="relative flex min-h-0 flex-1 flex-col items-center justify-center">
        {effectiveScreen === "chat" ? (
          <OnboardingChat
            title={titleText}
            messages={messages}
            isThinking={isThinking}
            liveTurn={liveTurn}
            welcomeFaqs={welcomeFaqs}
            replyOptions={replyOptions}
            prompt={prompt}
            onPromptChange={setPrompt}
            onSend={(message) => void sendMessage(message)}
            onAnswer={answerQuestion}
            onReact={reactToMessage}
            disabled={isInputDisabled}
          />
        ) : (
          <div className="flex w-full flex-col items-center gap-4 overflow-y-auto px-4 py-6">
            <OnboardingNameAgent
              value={agentName}
              disabled={isSending}
              onChange={handleAgentNameChange}
              onContinue={handleContinue}
              workflowDraft={workflowDraft}
            />
            <button
              type="button"
              onClick={handleStartOver}
              className="text-sm text-muted-foreground underline-offset-4 hover:underline"
            >
              Start over
            </button>
          </div>
        )}

        <div className="absolute inset-x-0 bottom-12 flex justify-center px-4">
          <ErrorBanner message={error} />
        </div>
      </main>

      <OnboardingFooter />
    </div>
  );
}