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
    <footer className="flex items-center justify-between px-8 pb-6 text-xs text-slate-400">
      <div className="flex items-center gap-3">
        <a href="/terms" className="hover:text-slate-500 transition-colors">Terms and Conditions</a>
        <span>·</span>
        <a href="/privacy" className="hover:text-slate-500 transition-colors">Privacy Policy</a>
      </div>
      <button
        onClick={handleSkip}
        className="text-slate-500 font-medium hover:text-ai-brand transition-colors"
      >
        Skip to Login
      </button>
    </footer>
  );
};
