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
    <footer className="flex items-center justify-between px-8 pb-6 text-xs text-[#94a3b8]">
      <div className="flex items-center gap-3">
        <a href="/terms" className="hover:text-[#64748b] transition-colors">Terms and Conditions</a>
        <span>·</span>
        <a href="/privacy" className="hover:text-[#64748b] transition-colors">Privacy Policy</a>
      </div>
      <button
        onClick={handleSkip}
        className="text-[#64748b] font-medium hover:text-[#5b4bff] transition-colors"
      >
        Skip to Login
      </button>
    </footer>
  );
};
