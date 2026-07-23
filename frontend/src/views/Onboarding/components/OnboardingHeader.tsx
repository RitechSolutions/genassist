import { GenAssistLogo } from "@/components/GenAssistLogo";

export const OnboardingHeader = () => (
  <header className="flex items-center px-8 py-5">
    <GenAssistLogo
      aria-label="GenAssist"
      className="h-7 w-auto text-zinc-900 dark:text-zinc-100"
    />
  </header>
);
