import { useCallback } from "react";

export const OnboardingFooter = () => {

  // temporary skip handler
  const handleSkip = useCallback((event: React.MouseEvent) => {
    event.preventDefault();
    try {
      localStorage.setItem("skip_onboarding", "true");
    } catch (error) {
      // ignore write errors
    }
    window.dispatchEvent(new Event("skip-onboarding"));
    window.location.href = "/dashboard";
  }, []);

  return (
    <footer className="flex items-center justify-between px-8 pb-8 text-sm text-[#6b7280]">
      <div className="flex items-center gap-3">
        <a href="/terms" className="hover:text-[#4f46e5]">Terms and Conditions</a>
        <span className="text-[#9ca3af]">•</span>
        <a href="/privacy" className="hover:text-[#4f46e5]">Privacy Policy</a>
      </div>
      <a href="/dashboard" onClick={handleSkip} className="text-[#4f46e5] font-semibold hover:underline">
        Skip to Dashboard
      </a>
    </footer>
  );
};