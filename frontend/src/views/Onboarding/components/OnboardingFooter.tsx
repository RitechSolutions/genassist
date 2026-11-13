import { useCallback } from "react";

export const OnboardingFooter = () => {
  const handleSkip = useCallback((event: React.MouseEvent) => {
    event.preventDefault();
    try {
      localStorage.setItem("skip_onboarding", "true");
    } catch {
      // ignore write errors
    }
    window.dispatchEvent(new Event("skip-onboarding"));
    window.location.href = "/login";
  }, []);

  return (
    // Laid over the bottom of the page so the grid runs beneath it; only the links take the pointer.
    <footer className="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex items-center justify-between px-8 pb-6 text-xs text-muted-foreground">
      <div className="pointer-events-auto flex items-center gap-3">
        <a href="/terms" className="transition-colors hover:text-foreground">Terms and Conditions</a>
        <span>·</span>
        <a href="/privacy" className="transition-colors hover:text-foreground">Privacy Policy</a>
      </div>
      <button
        onClick={handleSkip}
        className="pointer-events-auto font-medium text-muted-foreground transition-colors hover:text-ai-brand"
      >
        Skip to Login
      </button>
    </footer>
  );
};
