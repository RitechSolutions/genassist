import { useEffect, useMemo, useState } from "react";
import { ErrorBanner } from "@/views/Onboarding/components/ErrorBanner";
import { OnboardingFooter } from "@/views/Onboarding/components/OnboardingFooter";
import { OnboardingHeader } from "@/views/Onboarding/components/OnboardingHeader";
import { OnboardingHero } from "@/views/Onboarding/components/OnboardingHero";
import { OnboardingInput } from "@/views/Onboarding/components/Onboardinginput";
import { useOnboardingChat } from "@/views/Onboarding/hooks/useOnboardingChat";
import { parseInteractiveContentBlocks } from "genassist-chat-react";

export default function Onboarding() {
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
  } = useOnboardingChat();

  const [showCongrats, setShowCongrats] = useState(true);
  const [showQuickActions, setShowQuickActions] = useState(false);

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

  const isInputDisabled = !hasConfig || isSending;

  return (
    <div className="min-h-screen flex flex-col bg-white text-[#111827] animate-fade-up">
      <OnboardingHeader />

      <main className="flex-1 flex flex-col items-center justify-center">
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

        <ErrorBanner message={error} />
      </main>

      <OnboardingFooter />
    </div>
  );
}