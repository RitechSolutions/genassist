import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-hot-toast";
import { getAgentConfig, updateAgentConfig } from "@/services/api";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { Textarea } from "@/components/textarea";
import { Card } from "@/components/card";
import { Save, Loader2, Upload, X, FileJson } from "lucide-react";

interface SecurityPanelProps {
  agentId?: string;
}

export const SecurityPanel = ({
  agentId: agentIdProp,
}: SecurityPanelProps) => {
  const { agentId: agentIdParam } = useParams<{ agentId: string }>();
  const agentId = agentIdProp ?? agentIdParam;
  const [loading, setLoading] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [configName, setConfigName] = useState<string | null>(null);

  // Token-based auth settings
  const [tokenBasedAuth, setTokenBasedAuth] = useState<boolean>(false);
  const [tokenExpirationMinutes, setTokenExpirationMinutes] = useState<string>("");

  // CORS settings
  const [corsAllowedOrigins, setCorsAllowedOrigins] = useState<string>("");

  // Rate limiting settings
  const [rateLimitStartPerMinute, setRateLimitStartPerMinute] = useState<string>("");
  const [rateLimitStartPerHour, setRateLimitStartPerHour] = useState<string>("");
  const [rateLimitUpdatePerMinute, setRateLimitUpdatePerMinute] = useState<string>("");
  const [rateLimitUpdatePerHour, setRateLimitUpdatePerHour] = useState<string>("");

  // reCAPTCHA settings
  const [recaptchaEnabled, setRecaptchaEnabled] = useState<boolean>(false);
  const [recaptchaProjectId, setRecaptchaProjectId] = useState<string>("");
  const [recaptchaSiteKey, setRecaptchaSiteKey] = useState<string>("");
  const [recaptchaMinScore, setRecaptchaMinScore] = useState<string>("");
  const [gcpSvcAccountJson, setGcpSvcAccountJson] = useState<string>("");
  const [gcpSvcAccountFile, setGcpSvcAccountFile] = useState<File | null>(null);
  const [gcpSvcAccountFileName, setGcpSvcAccountFileName] = useState<string>("");

  useEffect(() => {
    if (!agentId) return;

    const loadAgentConfig = async () => {
      try {
        setLoading(true);
        const config = await getAgentConfig(agentId);
        setConfigName(config.name ?? null);

        // Security settings (nested object)
        const securitySettings = config.security_settings;
        
        // Token-based auth (now in security_settings)
        setTokenBasedAuth(securitySettings?.token_based_auth ?? false);
        setTokenExpirationMinutes(
          securitySettings?.token_expiration_minutes?.toString() ?? ""
        );

        // CORS
        setCorsAllowedOrigins(securitySettings?.cors_allowed_origins ?? "");

        // Rate limiting
        setRateLimitStartPerMinute(
          securitySettings?.rate_limit_conversation_start_per_minute?.toString() ?? ""
        );
        setRateLimitStartPerHour(
          securitySettings?.rate_limit_conversation_start_per_hour?.toString() ?? ""
        );
        setRateLimitUpdatePerMinute(
          securitySettings?.rate_limit_conversation_update_per_minute?.toString() ?? ""
        );
        setRateLimitUpdatePerHour(
          securitySettings?.rate_limit_conversation_update_per_hour?.toString() ?? ""
        );

        // reCAPTCHA
        setRecaptchaEnabled(securitySettings?.recaptcha_enabled ?? false);
        setRecaptchaProjectId(securitySettings?.recaptcha_project_id ?? "");
        setRecaptchaSiteKey(securitySettings?.recaptcha_site_key ?? "");
        setRecaptchaMinScore(securitySettings?.recaptcha_min_score ?? "");
        
        // Decode base64 GCP service account if present
        if (securitySettings?.gcp_svc_account) {
          try {
            const decoded = atob(securitySettings.gcp_svc_account);
            const jsonObj = JSON.parse(decoded);
            setGcpSvcAccountJson(JSON.stringify(jsonObj, null, 2));
          } catch (e) {
            // If decoding fails, just show empty
            setGcpSvcAccountJson("");
          }
        } else {
          setGcpSvcAccountJson("");
        }
        setGcpSvcAccountFile(null);
        setGcpSvcAccountFileName("");
      } catch (error) {
        toast.error("Failed to load security settings");
      } finally {
        setLoading(false);
      }
    };

    loadAgentConfig();
  }, [agentId]);

  const handleGcpFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type !== "application/json" && !file.name.endsWith(".json")) {
      toast.error("Please select a valid JSON file");
      e.target.value = "";
      return;
    }

    try {
      const text = await file.text();
      // Validate JSON
      JSON.parse(text);
      setGcpSvcAccountJson(text);
      setGcpSvcAccountFile(file);
      setGcpSvcAccountFileName(file.name);
      e.target.value = "";
    } catch (error) {
      toast.error("Invalid JSON file. Please check the file format.");
      e.target.value = "";
    }
  };

  const handleRemoveGcpFile = () => {
    setGcpSvcAccountFile(null);
    setGcpSvcAccountFileName("");
    setGcpSvcAccountJson("");
  };

  const handleSave = async () => {
    if (!agentId) return;

    try {
      setSaving(true);

      // Convert GCP service account JSON to base64
      let gcpSvcAccountBase64: string | null = null;
      if (gcpSvcAccountJson.trim()) {
        try {
          // Validate JSON
          const jsonObj = JSON.parse(gcpSvcAccountJson);
          // Convert to base64
          gcpSvcAccountBase64 = btoa(JSON.stringify(jsonObj));
        } catch (error) {
          toast.error("Invalid JSON format for GCP Service Account");
          setSaving(false);
          return;
        }
      }

      const updateData: any = {
        security_settings: {
          token_based_auth: tokenBasedAuth,
          token_expiration_minutes: tokenExpirationMinutes
            ? parseInt(tokenExpirationMinutes)
            : null,
          cors_allowed_origins: corsAllowedOrigins || null,
          rate_limit_conversation_start_per_minute: rateLimitStartPerMinute
            ? parseInt(rateLimitStartPerMinute)
            : null,
          rate_limit_conversation_start_per_hour: rateLimitStartPerHour
            ? parseInt(rateLimitStartPerHour)
            : null,
          rate_limit_conversation_update_per_minute: rateLimitUpdatePerMinute
            ? parseInt(rateLimitUpdatePerMinute)
            : null,
          rate_limit_conversation_update_per_hour: rateLimitUpdatePerHour
            ? parseInt(rateLimitUpdatePerHour)
            : null,
          recaptcha_enabled: recaptchaEnabled,
          recaptcha_project_id: recaptchaProjectId || null,
          recaptcha_site_key: recaptchaSiteKey || null,
          recaptcha_min_score: recaptchaMinScore || null,
          gcp_svc_account: gcpSvcAccountBase64,
        },
      };

      await updateAgentConfig(agentId, updateData);
      toast.success("Security settings saved successfully");
      
      // Reload the config to show updated values
      const updatedConfig = await getAgentConfig(agentId);
      const securitySettings = updatedConfig.security_settings;
      
      // Update state with fresh data
      const updatedSecuritySettings = updatedConfig.security_settings;
      setTokenBasedAuth(updatedSecuritySettings?.token_based_auth ?? false);
      setTokenExpirationMinutes(
        securitySettings?.token_expiration_minutes?.toString() ?? ""
      );
      setCorsAllowedOrigins(securitySettings?.cors_allowed_origins ?? "");
      setRateLimitStartPerMinute(
        securitySettings?.rate_limit_conversation_start_per_minute?.toString() ?? ""
      );
      setRateLimitStartPerHour(
        securitySettings?.rate_limit_conversation_start_per_hour?.toString() ?? ""
      );
      setRateLimitUpdatePerMinute(
        securitySettings?.rate_limit_conversation_update_per_minute?.toString() ?? ""
      );
      setRateLimitUpdatePerHour(
        securitySettings?.rate_limit_conversation_update_per_hour?.toString() ?? ""
      );
      setRecaptchaEnabled(securitySettings?.recaptcha_enabled ?? false);
      setRecaptchaProjectId(securitySettings?.recaptcha_project_id ?? "");
      setRecaptchaSiteKey(securitySettings?.recaptcha_site_key ?? "");
      setRecaptchaMinScore(securitySettings?.recaptcha_min_score ?? "");
      
      // Decode base64 GCP service account if present
      if (securitySettings?.gcp_svc_account) {
        try {
          const decoded = atob(securitySettings.gcp_svc_account);
          const jsonObj = JSON.parse(decoded);
          setGcpSvcAccountJson(JSON.stringify(jsonObj, null, 2));
        } catch (e) {
          setGcpSvcAccountJson("");
        }
      } else {
        setGcpSvcAccountJson("");
      }
      setGcpSvcAccountFile(null);
      setGcpSvcAccountFileName("");
    } catch (error: any) {
      toast.error(error?.message || "Failed to save security settings");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-8">
        <div className="flex justify-center items-center py-12">
          <div className="text-sm text-gray-500">Loading security settings...</div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between border-b border-gray-200 pb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              {configName ? `Security Settings for ${configName}` : "Security Settings"}
            </h3>
            <p className="text-sm text-gray-500 mt-1">
              Configure authentication, CORS, rate limiting, and reCAPTCHA settings
            </p>
          </div>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-2" />
                Save Changes
              </>
            )}
          </Button>
        </div>

        {/* Token-based Authentication */}
        <div className="space-y-4 border-b border-gray-200 pb-6">
          <div>
            <h4 className="text-base font-semibold text-gray-900 mb-1">
              Token-based Authentication
            </h4>
            <p className="text-sm text-gray-500">
              Configure JWT token authentication for secure API access
            </p>
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="token-based-auth">Enable Token-based Auth</Label>
                <p className="text-sm text-gray-500">
                  Require JWT token for conversation updates instead of API key
                </p>
              </div>
              <Switch
                id="token-based-auth"
                checked={tokenBasedAuth}
                onCheckedChange={setTokenBasedAuth}
              />
            </div>
            {tokenBasedAuth && (
              <div className="space-y-2">
                <Label htmlFor="token-expiration">
                  Token Expiration (minutes)
                </Label>
                <Input
                  id="token-expiration"
                  type="number"
                  min="1"
                  value={tokenExpirationMinutes}
                  onChange={(e) => setTokenExpirationMinutes(e.target.value)}
                  placeholder="60 (default)"
                />
                <p className="text-xs text-gray-500">
                  Leave empty to use global default (60 minutes)
                </p>
              </div>
            )}
          </div>
        </div>

        {/* CORS Settings */}
        <div className="space-y-4 border-b border-gray-200 pb-6">
          <div>
            <h4 className="text-base font-semibold text-gray-900 mb-1">CORS Settings</h4>
            <p className="text-sm text-gray-500">
              Configure allowed origins for cross-origin requests
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="cors-origins">Allowed Origins</Label>
            <Textarea
              id="cors-origins"
              value={corsAllowedOrigins}
              onChange={(e) => setCorsAllowedOrigins(e.target.value)}
              placeholder="https://example.com, https://app.example.com"
              rows={3}
            />
            <p className="text-xs text-gray-500">
              Comma-separated list of allowed CORS origins. Leave empty to use
              global default.
            </p>
          </div>
        </div>

        {/* Rate Limiting */}
        <div className="space-y-4 border-b border-gray-200 pb-6">
          <div>
            <h4 className="text-base font-semibold text-gray-900 mb-1">Rate Limiting</h4>
            <p className="text-sm text-gray-500">
              Set rate limits for conversation endpoints per agent
            </p>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="rate-limit-start-minute">
                Conversation Start (per minute)
              </Label>
              <Input
                id="rate-limit-start-minute"
                type="number"
                min="1"
                value={rateLimitStartPerMinute}
                onChange={(e) => setRateLimitStartPerMinute(e.target.value)}
                placeholder="10 (default)"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="rate-limit-start-hour">
                Conversation Start (per hour)
              </Label>
              <Input
                id="rate-limit-start-hour"
                type="number"
                min="1"
                value={rateLimitStartPerHour}
                onChange={(e) => setRateLimitStartPerHour(e.target.value)}
                placeholder="100 (default)"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="rate-limit-update-minute">
                Conversation Update (per minute)
              </Label>
              <Input
                id="rate-limit-update-minute"
                type="number"
                min="1"
                value={rateLimitUpdatePerMinute}
                onChange={(e) => setRateLimitUpdatePerMinute(e.target.value)}
                placeholder="30 (default)"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="rate-limit-update-hour">
                Conversation Update (per hour)
              </Label>
              <Input
                id="rate-limit-update-hour"
                type="number"
                min="1"
                value={rateLimitUpdatePerHour}
                onChange={(e) => setRateLimitUpdatePerHour(e.target.value)}
                placeholder="500 (default)"
              />
            </div>
          </div>
          <p className="text-xs text-gray-500">
            Leave empty to use global defaults. These limits apply per
            conversation/agent.
          </p>
        </div>

        {/* reCAPTCHA Settings */}
        <div className="space-y-4">
          <div>
            <h4 className="text-base font-semibold text-gray-900 mb-1">reCAPTCHA Settings</h4>
            <p className="text-sm text-gray-500">
              Configure Google reCAPTCHA Enterprise for bot protection
            </p>
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="recaptcha-enabled">Enable reCAPTCHA</Label>
                <p className="text-sm text-gray-500">
                  Enable Google reCAPTCHA Enterprise verification
                </p>
              </div>
              <Switch
                id="recaptcha-enabled"
                checked={recaptchaEnabled}
                onCheckedChange={setRecaptchaEnabled}
              />
            </div>
            {recaptchaEnabled && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="recaptcha-project-id">Project ID</Label>
                  <Input
                    id="recaptcha-project-id"
                    value={recaptchaProjectId}
                    onChange={(e) => setRecaptchaProjectId(e.target.value)}
                    placeholder="your-project-id"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="recaptcha-site-key">Site Key</Label>
                  <Input
                    id="recaptcha-site-key"
                    value={recaptchaSiteKey}
                    onChange={(e) => setRecaptchaSiteKey(e.target.value)}
                    placeholder="your-site-key"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="recaptcha-min-score">Minimum Score (0.0-1.0)</Label>
                  <Input
                    id="recaptcha-min-score"
                    type="text"
                    value={recaptchaMinScore}
                    onChange={(e) => setRecaptchaMinScore(e.target.value)}
                    placeholder="0.5"
                  />
                </div>
                <div className="space-y-3">
                  <Label htmlFor="gcp-svc-account">
                    GCP Service Account JSON
                  </Label>
                  
                  {/* File Upload Option */}
                  <div className="space-y-2">
                    <label
                      htmlFor="gcp-file-upload"
                      className="flex items-center justify-center w-full border-2 border-dashed border-gray-300 rounded-lg p-4 cursor-pointer hover:border-gray-400 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex flex-col items-center gap-2">
                        <Upload className="h-6 w-6 text-gray-400" />
                        <span className="text-sm font-medium text-gray-600">
                          {gcpSvcAccountFileName || "Upload JSON file"}
                        </span>
                        <span className="text-xs text-gray-500">
                          Click to select a JSON file
                        </span>
                      </div>
                      <input
                        id="gcp-file-upload"
                        type="file"
                        accept=".json,application/json"
                        onChange={handleGcpFileChange}
                        className="hidden"
                      />
                    </label>
                    
                    {gcpSvcAccountFileName && (
                      <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200">
                        <div className="flex items-center gap-2">
                          <FileJson className="h-5 w-5 text-gray-600" />
                          <span className="text-sm font-medium text-gray-700">
                            {gcpSvcAccountFileName}
                          </span>
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={handleRemoveGcpFile}
                          className="h-8 w-8 p-0"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    )}
                  </div>

                  {/* Or JSON Text Input */}
                  <div className="relative">
                    <div className="absolute inset-0 flex items-center">
                      <div className="w-full border-t border-gray-300"></div>
                    </div>
                    <div className="relative flex justify-center text-xs uppercase">
                      <span className="bg-white px-2 text-gray-500">Or paste JSON</span>
                    </div>
                  </div>

                  <Textarea
                    id="gcp-svc-account"
                    value={gcpSvcAccountJson}
                    onChange={(e) => setGcpSvcAccountJson(e.target.value)}
                    placeholder='{"type": "service_account", "project_id": "...", ...}'
                    rows={8}
                    className="font-mono text-sm"
                  />
                  <p className="text-xs text-gray-500">
                    Paste your GCP service account JSON content here, or upload a JSON file above
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
};

export default SecurityPanel;
