import { useState, useEffect } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import toast from "react-hot-toast";
import { LoginForm } from "../components/LoginForm";
import { useAuth } from "../hooks/useAuth";
import { ForcePasswordUpdateDialog } from "../components/ForcePasswordUpdateDialog";
import { fetchUserPermissions } from "@/services/auth";
import { TermsAndPolicyNotice } from "@/components/TermsAndPolicyNotice";
import { AuthMockupPanel } from "@/components/AuthMockupPanel";
import { useFeatureFlag } from "@/context/FeatureFlagContext";
import {
  createWorkflowFromWizard,
  createWorkflowFromBuilder,
} from "@/services/workflows";
import {
  WORKFLOW_DRAFT_STORAGE_KEY,
  AGENT_NAME_STORAGE_KEY,
} from "@/views/Onboarding/pages/Onboarding";
import { GenAssistLogo } from "@/components/GenAssistLogo";

interface ForceUpdateInfo {
  username: string;
  oldPassword: string;
  token: string;
}

const LoginPage = () => {
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const { refreshFlags } = useFeatureFlag();
  const navigate = useNavigate();
  const location = useLocation();
  const [forceUpdateInfo, setForceUpdateInfo] =
    useState<ForceUpdateInfo | null>(null);
  const [isForceUpdateDialogOpen, setIsForceUpdateDialogOpen] = useState(false);
  const [key, setKey] = useState(Date.now());

  // Show success message if redirected from password change
  useEffect(() => {
    if (location.state?.message) {
      toast.success(location.state.message);
      // Clear the state to prevent showing the message again on refresh
      window.history.replaceState({}, document.title);
    }
  }, [location.state?.message]);

  // Helper function to check if password update is required based on force_upd_pass_date
  const isPasswordUpdateRequired = (forceUpdPassDate: string): boolean => {
    if (!forceUpdPassDate) return false;

    try {
      const forceUpdateDate = new Date(forceUpdPassDate);
      const now = new Date();

      // If force_upd_pass_date is now or in the past, password update is required
      return forceUpdateDate <= now;
    } catch (error) {
      return false;
    }
  };

  const handleLogin = async (
    username: string,
    password: string,
    tenant: string,
    keepSignedIn: boolean
  ) => {
    setIsLoading(true);

    try {
      // Store tenant in localStorage
      localStorage.setItem("tenant_id", tenant);
      
      const response = await login(username, password, tenant);

      if (response?.access_token) {
        // Login was successful, store tokens
        localStorage.setItem("access_token", response.access_token);
        localStorage.setItem("refresh_token", response.refresh_token ?? "");
        const tokenType = response.token_type || "bearer";
        localStorage.setItem(
          "token_type",
          tokenType.toLowerCase() === "bearer" ? "Bearer" : tokenType
        );
        localStorage.setItem("isAuthenticated", "true");

        // Store force_upd_pass_date if provided
        if (response.force_upd_pass_date) {
          localStorage.setItem(
            "force_upd_pass_date",
            response.force_upd_pass_date
          );
        }

        // Check if password update is required
        const needsUpdate =
          response.force_upd_pass_date &&
          isPasswordUpdateRequired(response.force_upd_pass_date);

        if (needsUpdate) {
          // Password update is required - show the dialog
          setForceUpdateInfo({
            username,
            oldPassword: password,
            token: response.access_token,
          });
          setIsForceUpdateDialogOpen(true);
          return;
        }

        // No password update required - proceed with normal login flow
        // Execute post-login actions sequentially to avoid race conditions
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

        // Check for pending onboarding workflow draft
        const pendingDraft = localStorage.getItem(WORKFLOW_DRAFT_STORAGE_KEY);
        const pendingName = localStorage.getItem(AGENT_NAME_STORAGE_KEY);
        const cameFromOnboarding = location.state?.from?.pathname === "/onboarding";

        // Mark onboarding as done early so any redirect/reload won't loop back
        if (cameFromOnboarding) {
          localStorage.setItem("skip_onboarding", "true");
          window.dispatchEvent(new Event("skip-onboarding"));
        }

        if (pendingDraft && pendingName) {
          try {
            let hasEdges = false;
            try {
              const parsed = JSON.parse(pendingDraft);
              hasEdges = Array.isArray(parsed?.edges) && parsed.edges.length > 0;
            } catch {
              // not valid JSON, fall through to wizard
            }

            const wizardResponse = hasEdges
              ? await createWorkflowFromBuilder({ workflow_name: pendingName, workflow_json: pendingDraft })
              : await createWorkflowFromWizard({ workflow_name: pendingName, workflow_json: pendingDraft });

            // Clean up onboarding data
            localStorage.removeItem(WORKFLOW_DRAFT_STORAGE_KEY);
            localStorage.removeItem(AGENT_NAME_STORAGE_KEY);
            localStorage.setItem("skip_onboarding", "true");
            window.dispatchEvent(new Event("skip-onboarding"));

            toast.success("Agent created successfully!");

            if (wizardResponse?.agent_id) {
              window.location.href = `/ai-agents/workflow/${wizardResponse.agent_id}?setup=true`;
            } else if (wizardResponse?.url) {
              const sep = wizardResponse.url.includes("?") ? "&" : "?";
              window.location.href = `${wizardResponse.url}${sep}setup=true`;
            } else if (wizardResponse?.id) {
              window.location.href = `/ai-agents/workflow/${wizardResponse.id}?setup=true`;
            } else {
              window.location.href = "/dashboard";
            }
            return;
          } catch (error) {
            toast.error("Failed to create workflow. Redirecting to dashboard.");
            localStorage.removeItem(WORKFLOW_DRAFT_STORAGE_KEY);
            localStorage.removeItem(AGENT_NAME_STORAGE_KEY);
          }
        }

        toast.success("Logged in successfully.");
        const from = location.state?.from?.pathname || "/dashboard";
        // Never redirect back to onboarding — go to dashboard instead
        window.location.href = from === "/onboarding" ? "/dashboard" : from;
      } else {
        toast.error("Failed to log in.");
      }
    } catch (error) {
      toast.error("Failed to log in.");
    } finally {
      setIsLoading(false);
    }
  };

  const handlePasswordUpdated = () => {
    setForceUpdateInfo(null);
    setIsForceUpdateDialogOpen(false);
    // Clear the stored force_upd_pass_date since password was updated
    localStorage.removeItem("force_upd_pass_date");
    const from = location.state?.from;
    navigate("/login", {
      replace: true,
      state: {
        message:
          "Password updated successfully. Please log in with your new password.",
        from,
      },
    });
  };

  return (
    <div className="min-h-screen flex flex-col">
      <div className="flex-1 grid md:grid-cols-2">
        <div className="flex items-center justify-center p-4 bg-white">
          <div className="w-full max-w-md space-y-6">
            <div className="space-y-2">
              <GenAssistLogo width={200} height={52} />

              <h1 className="text-3xl font-bold tracking-tight">Sign in</h1>
              <p className="text-zinc-500">
                Log in to unlock tailored content and stay connected with your
                community.
              </p>
            </div>

            <LoginForm key={key} onSubmit={handleLogin} isLoading={isLoading} />

            <div className="text-center text-sm mt-8">
              <span className="text-zinc-500">Don't have an account? </span>
              <Link
                to="/register"
                state={location.state}
                className="text-black hover:underline font-medium"
              >
                Sign up
              </Link>
            </div>

            <TermsAndPolicyNotice mode="signin" className="mt-2" />
          </div>
        </div>
        <AuthMockupPanel />
      </div>

      {forceUpdateInfo && (
        <ForcePasswordUpdateDialog
          isOpen={isForceUpdateDialogOpen}
          onOpenChange={setIsForceUpdateDialogOpen}
          username={forceUpdateInfo.username}
          oldPassword={forceUpdateInfo.oldPassword}
          token={forceUpdateInfo.token}
          onPasswordUpdated={handlePasswordUpdated}
        />
      )}
    </div>
  );
};

export default LoginPage;
