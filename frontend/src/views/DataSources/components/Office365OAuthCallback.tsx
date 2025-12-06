// Office365OAuthCallback.tsx
import { useEffect, useState, useRef } from "react";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";
import { toast } from "react-hot-toast";
import { Loader2 } from "lucide-react";
import { apiRequest } from "@/config/api";

export function Office365OAuthCallback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [isProcessing, setIsProcessing] = useState(true);
  const [statusMessage, setStatusMessage] = useState(
    "Processing Office365 Authorization"
  );
  const [shouldRedirect, setShouldRedirect] = useState(false);
  const [redirectDelay, setRedirectDelay] = useState(0);
  const hasProcessed = useRef(false);
  const location = useLocation();

  useEffect(() => {
    if (shouldRedirect && redirectDelay > 0) {
      const timer = setTimeout(() => {
        navigate("/data-sources", { replace: true });
      }, redirectDelay);

      return () => clearTimeout(timer);
    }
  }, [shouldRedirect, redirectDelay, navigate]);

  useEffect(() => {
    if (hasProcessed.current) return;

    const processOAuthCallback = async () => {
      const code = searchParams.get("code");
      const state = searchParams.get("state");
      const error = searchParams.get("error");

      const redirect_uri = `${window.location.origin}${location.pathname}`;
      hasProcessed.current = true;

      if (error) {
        toast.error("Office 365 authorization failed.");
        setStatusMessage("Authorization failed. Redirecting...");
        setIsProcessing(false);
        setShouldRedirect(true);
        setRedirectDelay(1500);
        return;
      }

      if (!code || !state) {
        toast.error("Invalid Office 365 authorization response.");
        setStatusMessage("Invalid response. Redirecting...");
        setIsProcessing(false);
        setShouldRedirect(true);
        setRedirectDelay(1500);
        return;
      }

      try {
        await apiRequest("POST", "/office365/oauth/callback", {
          code,
          state,
          redirect_uri: redirect_uri,
        });

        toast.success("Office 365 connected successfully.");
        setStatusMessage("Connected successfully! Redirecting...");
        setIsProcessing(false);
        setShouldRedirect(true);
        setRedirectDelay(1000);
      } catch (err) {
        toast.error("Failed to complete Office 365 authorization.");
        setStatusMessage("Authorization failed. Redirecting...");
        setIsProcessing(false);
        setShouldRedirect(true);
        setRedirectDelay(1500);
      }
    };

    processOAuthCallback();
  }, [searchParams]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="text-center bg-white p-8 rounded-lg shadow-xl max-w-lg w-full">
        <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4" />
        <p className="text-lg font-medium mb-2">{statusMessage}</p>
        <p className="text-sm text-gray-600">
          Please wait while we complete the setup...
        </p>
      </div>
    </div>
  );
}
