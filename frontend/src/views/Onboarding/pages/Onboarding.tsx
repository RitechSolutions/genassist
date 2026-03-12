import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorBanner } from "@/views/Onboarding/components/ErrorBanner";
import { OnboardingFooter } from "@/views/Onboarding/components/OnboardingFooter";
import { OnboardingHeader } from "@/views/Onboarding/components/OnboardingHeader";
import { OnboardingHero } from "@/views/Onboarding/components/OnboardingHero";
import { OnboardingInput } from "@/views/Onboarding/components/Onboardinginput";
import { OnboardingNameAgent } from "@/views/Onboarding/components/OnboardingNameAgent";
import { useOnboardingChat } from "@/views/Onboarding/hooks/useOnboardingChat";
import { extractWorkflowDraftFromText, isWorkflowDraft } from "@/views/Onboarding/utils/extractWorkflowDraft";
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
    subtitleText,
    titleText,
    welcomeFaqs,
    hasUserStartedChat,
    isSending,
    error,
    hasConfig,
    handleSubmit,
    sendQuickAction,
  } = useOnboardingChat({ registrationStatus });

  const [showCongrats, setShowCongrats] = useState(true);
  const [showQuickActions, setShowQuickActions] = useState(false);
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

  const quickActions = useMemo(() => {
    if (!agentReply) {
      if (!hasUserStartedChat && welcomeFaqs.length) {
        return welcomeFaqs;
      }
      return [];
    }
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
  }, [agentReply, hasUserStartedChat, welcomeFaqs]);

  useEffect(() => {
    const congratsTimer = setTimeout(() => setShowCongrats(false), 1200);
    const quickActionsTimer = setTimeout(() => setShowQuickActions(true), 1400);
    return () => {
      clearTimeout(congratsTimer);
      clearTimeout(quickActionsTimer);
    };
  }, []);

  const extractedDraft = useMemo(() => {
    if (!agentReply) return null;
    return extractWorkflowDraftFromText(agentReply);
  }, [agentReply]);

  const effectiveScreen: OnboardingScreen = extractedDraft ? "name-agent" : screen;

  useEffect(() => {
    if (!extractedDraft) return;

    try {
      localStorage.setItem(WORKFLOW_DRAFT_STORAGE_KEY, extractedDraft.raw);
    } catch {
      // ignore
    }

    if (screen !== "name-agent") {
      setScreen("name-agent");
    }
  }, [extractedDraft, screen]);

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

  return (
    <div className="min-h-screen flex flex-col bg-[#fafbfc]">
      <OnboardingHeader />

      <main className="flex-1 flex flex-col items-center justify-center px-4 gap-8">
        {effectiveScreen === "chat" ? (
          <>
            <OnboardingHero
              showCongrats={showCongrats && !agentReply}
              showQuickActions={showQuickActions && quickActions.length > 0}
              subtitle={subtitleText}
              title={titleText}
              quickActions={quickActions}
              onQuickAction={sendQuickAction}
              disableQuickActions={isInputDisabled}
              messages={messages}
              isThinking={isThinking}
            />

            <OnboardingInput
              value={prompt}
              disabled={isInputDisabled}
              onChange={setPrompt}
              onSubmit={handleSubmit}
            />
          </>
        ) : (
          <OnboardingNameAgent
            value={agentName}
            disabled={isSending}
            onChange={handleAgentNameChange}
            onContinue={handleContinue}
            workflowDraft={extractedDraft?.parsed ?? null}
          />
        )}

        <ErrorBanner message={error} />
      </main>

      <OnboardingFooter />
    </div>
  );
}