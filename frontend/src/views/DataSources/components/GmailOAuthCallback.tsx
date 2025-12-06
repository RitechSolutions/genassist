import { useEffect, useState, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "react-hot-toast";
import { Loader2 } from "lucide-react";
import { apiRequest } from "@/config/api";

export function GmailOAuthCallback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [isProcessing, setIsProcessing] = useState(true);
  const [statusMessage, setStatusMessage] = useState(
    "Processing Gmail Authorization"
  );
  const [shouldRedirect, setShouldRedirect] = useState(false);
  const [redirectDelay, setRedirectDelay] = useState(0);
  const hasProcessed = useRef(false);

  // Handle redirect
  useEffect(() => {
    if (shouldRedirect && redirectDelay > 0) {
      const timer = setTimeout(() => {
        navigate("/data-sources", { replace: true });
      }, redirectDelay);

      return () => clearTimeout(timer);
    }
  }, [shouldRedirect, redirectDelay, navigate]);

  useEffect(() => {
    if (hasProcessed.current) {
      return;
    }

    const processOAuthCallback = async () => {
      const code = searchParams.get("code");
      const state = searchParams.get("state");
      const error = searchParams.get("error");

      hasProcessed.current = true;

      if (error) {
        // OAuth was cancelled or failed
        toast.error("Gmail authorization failed.");
        setStatusMessage("Authorization failed. Redirecting...");
        setIsProcessing(false);
        setShouldRedirect(true);
        setRedirectDelay(1500);
        return;
      }

      if (!code || !state) {
        // Invalid callback parameters
        toast.error("Invalid Gmail authorization response.");
        setStatusMessage("Invalid response. Redirecting...");
        setIsProcessing(false);
        setShouldRedirect(true);
        setRedirectDelay(1500);
        return;
      }

      try {
        // Call backend to process the OAuth code and update the datasource
        const baseUrl = `${window.location.protocol}//${
          window.location.hostname
        }${window.location.port ? `:${window.location.port}` : ""}`;
        const redirectUri = `${baseUrl}/gauth/callback`;

        await apiRequest("POST", "/gmail/oauth/callback", {
          code,
          state,
          redirect_uri: redirectUri,
        });

        toast.success("Gmail connected successfully.");
        setStatusMessage("Gmail connected successfully! Redirecting...");
        setIsProcessing(false);
        setShouldRedirect(true);
        setRedirectDelay(1000);
      } catch (error) {
        toast.error("Failed to complete Gmail authorization.");
        setStatusMessage("Authorization failed. Redirecting...");
        setIsProcessing(false);
        setShouldRedirect(true);
        setRedirectDelay(1500);
      }
    };

    processOAuthCallback();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
