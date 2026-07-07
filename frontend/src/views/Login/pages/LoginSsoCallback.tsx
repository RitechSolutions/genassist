import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import toast from "react-hot-toast";
import { completeMicrosoftSso, fetchUserPermissions } from "@/services/auth";
import { useFeatureFlag } from "@/context/FeatureFlagContext";
import { GenAssistLogo } from "@/components/GenAssistLogo";

const LoginSsoCallbackPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { refreshFlags } = useFeatureFlag();
  const ran = useRef(false);
  const [message, setMessage] = useState("Completing sign-in…");

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const run = async () => {
      const ssoCode = searchParams.get("sso_code");
      if (!ssoCode) {
        toast.error("Missing sign-in code. Try again from the login page.");
        navigate("/login", { replace: true });
        return;
      }

      try {
        const response = await completeMicrosoftSso(ssoCode);
        if (!response?.access_token) {
          toast.error("Sign-in failed. Please try again.");
          navigate("/login", { replace: true });
          return;
        }

        localStorage.setItem("access_token", response.access_token);
        localStorage.setItem("refresh_token", response.refresh_token ?? "");
        const tokenType = response.token_type || "bearer";
        localStorage.setItem(
          "token_type",
          tokenType.toLowerCase() === "bearer" ? "Bearer" : tokenType
        );
        localStorage.setItem("isAuthenticated", "true");

        if (response.force_upd_pass_date) {
          localStorage.setItem("force_upd_pass_date", response.force_upd_pass_date);
        } else {
          localStorage.removeItem("force_upd_pass_date");
        }

        try {
          await refreshFlags();
        } catch {
          // ignore
        }
        try {
          await fetchUserPermissions();
        } catch {
          // ignore
        }

        setMessage("Signed in. Redirecting…");
        toast.success("Logged in successfully.");
        window.location.href = "/dashboard";
      } catch {
        toast.error("Microsoft sign-in failed. Please try again.");
        navigate("/login", { replace: true });
      }
    };

    void run();
  }, [navigate, refreshFlags, searchParams]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-white">
      <GenAssistLogo width={180} height={47} className="mb-8" />
      <p className="text-zinc-600">{message}</p>
    </div>
  );
};

export default LoginSsoCallbackPage;
