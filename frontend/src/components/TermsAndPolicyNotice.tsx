import React from "react";
import { Link } from "react-router-dom";

interface TermsAndPolicyNoticeProps {
  mode: "signin" | "signup";
  className?: string;
}

export const TermsAndPolicyNotice: React.FC<TermsAndPolicyNoticeProps> = ({ mode, className }) => {
  const verb = mode === "signup" ? "signing up" : "signing in";
  return (
    <div className={"text-center text-xs text-muted-foreground " + (className ?? "") }>
      By {verb}, I agree to the GenAssist{" "}
      <Link to="/terms" className="text-foreground hover:underline">
        Terms of Service
      </Link>{" "}
      and{" "}
      <Link to="/privacy" className="text-foreground hover:underline">
        Privacy Policy
      </Link>
    </div>
  );
};

export default TermsAndPolicyNotice;
