import { Context, useContext, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { ErrorBanner } from "@/views/Onboarding/components/ErrorBanner";
import { OnboardingFooter } from "@/views/Onboarding/components/OnboardingFooter";
import { OnboardingHeader } from "@/views/Onboarding/components/OnboardingHeader";
import { OnboardingHero } from "@/views/Onboarding/components/OnboardingHero";
import { OnboardingInput } from "@/views/Onboarding/components/Onboardinginput";
import { OnboardingNameAgent } from "@/views/Onboarding/components/OnboardingNameAgent";
import { useOnboardingChat } from "@/views/Onboarding/hooks/useOnboardingChat";
import { extractWorkflowDraftFromText, isWorkflowDraft } from "@/views/Onboarding/utils/extractWorkflowDraft";
import { parseInteractiveContentBlocks } from "genassist-chat-react";
import { useAuth } from "@/views/Login/hooks/useAuth";
import { fetchUserPermissions } from "@/services/auth";
import { useFeatureFlag } from "@/context/FeatureFlagContext";
import {
  createWorkflowFromWizard,
  type WorkflowWizardResponse,
} from "@/services/workflows";
import { useRoutesContext } from "@/context/RoutesContext";
import { Link } from "react-router-dom";

type OnboardingScreen = "chat" | "name-agent";

const WORKFLOW_DRAFT_STORAGE_KEY = "onboarding_workflow_draft";
const AGENT_NAME_STORAGE_KEY = "onboarding_agent_name";

export default function Onboarding() {
  const { login } = useAuth();
  const { refreshFlags } = useFeatureFlag();

  // read the registration status from the routes context
  const registrationStatus = useRoutesContext().registrationStatus;

  const {
    prompt,
    setPrompt,
    agentReply,
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
  const [isLoggingIn, setIsLoggingIn] = useState(false);
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
    if (isLoggingIn) return;
    void handleContinueAsync();
  };

  const handleContinueAsync = async () => {
    const trimmedName = agentName.trim();
    if (!trimmedName) return;

    try {
      localStorage.setItem(AGENT_NAME_STORAGE_KEY, trimmedName);
    } catch {
      // ignore
    }

    setIsLoggingIn(true);

    const username =
      (import.meta.env.VITE_ONBOARDING_USERNAME as string) || "admin";
    const password =
      (import.meta.env.VITE_ONBOARDING_PASSWORD as string) || "genadmin";
    const tenant =
      localStorage.getItem("tenant_id") ||
      (import.meta.env.VITE_GENASSIST_CHAT_TENANT_ID as string) ||
      "";

    try {
      localStorage.setItem("tenant_id", tenant);
    } catch {
      // ignore
    }

    try {
      const response = await login(username, password, tenant);

      if (response?.access_token) {
        localStorage.setItem("access_token", response.access_token);
        localStorage.setItem("refresh_token", response.refresh_token ?? "");
        const tokenType = response.token_type || "bearer";
        localStorage.setItem(
          "token_type",
          tokenType.toLowerCase() === "bearer" ? "Bearer" : tokenType
        );
        localStorage.setItem("isAuthenticated", "true");

        try {
          await refreshFlags();
        } catch (error) {
          // ignore
        }

        try {
          await fetchUserPermissions();
        } catch (error) {
          // ignore
        }

        const workflowName =
          localStorage.getItem(AGENT_NAME_STORAGE_KEY) || trimmedName;
        const workflowJson =
          localStorage.getItem(WORKFLOW_DRAFT_STORAGE_KEY) || "";
        let wizardResponse: WorkflowWizardResponse | null = null;

        if (workflowName && workflowJson) {
          try {
            wizardResponse = await createWorkflowFromWizard({
              workflow_name: workflowName,
              workflow_json: workflowJson,
            });
            if (!wizardResponse) {
              toast.error("Failed to create workflow from onboarding.");
            }
          } catch (error) {
            toast.error("Failed to create workflow from onboarding.");
          }
        } else {
          toast.error("Missing workflow data from onboarding.");
        }

        try {
          localStorage.setItem("skip_onboarding", "true");
        } catch {
          // ignore
        }
        window.dispatchEvent(new Event("skip-onboarding"));

        toast.success("Logged in successfully.");
        if (wizardResponse?.agent_id) {
          window.location.href = `/ai-agents/workflow/${wizardResponse.agent_id}`;
        } else if (wizardResponse?.url) {
          window.location.href = wizardResponse.url;
        } else if (wizardResponse?.id) {
          window.location.href = `/ai-agents/workflow/${wizardResponse.id}`;
        } else {
          window.location.href = "/dashboard";
        }
      } else {
        toast.error("Failed to log in.");
      }
    } catch (error) {
      toast.error("Failed to log in.");
    } finally {
      setIsLoggingIn(false);
    }
  };

  const ExistingOnboarding = () => (
    <main className="flex-1 flex flex-col items-center justify-center">
      <div className="h-32" />
      <p className="text-lg font-semibold text-[#0f172a]">🎉 Welcome Back!</p>
      <div className="w-full max-w-2xl bg-white  relative px-4 py-5 flex flex-col items-center justify-center">
        <p className="text-md text-[#9ca3af]">You are already registered. Please continue to the <Link to="/dashboard" className="text-[#4f46e5] font-semibold hover:underline">dashboard</Link>.</p>
      </div>
    </main>
  );

  const NewOnboarding = () => (
    <main className="flex-1 flex flex-col items-center justify-center">
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
        />

        <div className="h-32" />

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
        disabled={isSending || isLoggingIn || registrationStatus === "existing"}
        onChange={handleAgentNameChange}
        onContinue={handleContinue}
      />
    )}

    <ErrorBanner message={error} />
  </main>
  );

  return (
    <div className="min-h-screen flex flex-col bg-white text-[#111827] animate-fade-up">
      <OnboardingHeader />

      {registrationStatus === "existing" ? (
        <ExistingOnboarding />
      ) : (
        <NewOnboarding />
      )}

      <OnboardingFooter />
    </div>
  );
}