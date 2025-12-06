import React from "react";
import { Link } from "react-router-dom";

interface TermsAndPolicyNoticeProps {
  mode: "signin" | "signup";
  className?: string;
}

export const TermsAndPolicyNotice: React.FC<TermsAndPolicyNoticeProps> = ({ mode, className }) => {
  const verb = mode === "signup" ? "signing up" : "signing in";
  return (
    <div className={"text-center text-xs text-zinc-500 " + (className ?? "") }>
      By {verb}, I agree to the GenAssist{" "}
      <Link to="/terms" className="text-black hover:underline">
        Terms of Service
      </Link>{" "}
      and{" "}
      <Link to="/privacy" className="text-black hover:underline">
        Privacy Policy
      </Link>
    </div>
  );
};

export default TermsAndPolicyNotice;
