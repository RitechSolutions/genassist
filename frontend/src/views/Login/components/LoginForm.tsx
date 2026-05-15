import { useEffect, useState } from "react";
import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/checkbox";
import { Link } from "react-router-dom";
import { PasswordInput } from "@/components/PasswordInput";
import { getApiUrl } from "@/config/api";

interface LoginFormProps {
  onSubmit: (username: string, password: string, tenant: string, keepSignedIn: boolean) => void;
  isLoading: boolean;
}

const isMultiTenantEnabled = import.meta.env.VITE_MULTI_TENANT_ENABLED === "true";

export const LoginForm = ({ onSubmit, isLoading }: LoginFormProps) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [tenant, setTenant] = useState("");
  const [keepSignedIn, setKeepSignedIn] = useState(false);
  const [microsoftSsoEnabled, setMicrosoftSsoEnabled] = useState(false);

  useEffect(() => {
    const sso_microsoft_enabled = import.meta.env.VITE_SSO_MICROSOFT_ENABLED === "true";
    setMicrosoftSsoEnabled(sso_microsoft_enabled);

    if (!sso_microsoft_enabled) return;

    let cancelled = false;
    (async () => {
      try {
        const base = await getApiUrl();
        const r = await fetch(`${base}auth/sso/microsoft/status`);
        if (!r.ok) return;
        const data = (await r.json()) as { microsoft_sso_enabled?: boolean };
        if (!cancelled && data.microsoft_sso_enabled) {
          setMicrosoftSsoEnabled(true);
        }
      } catch {
        // ignore — SSO button stays hidden
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleMicrosoftSignIn = async () => {
    const base = await getApiUrl();
    const u = new URL(`${base.replace(/\/?$/, "/")}auth/sso/microsoft/start`);
    if (tenant.trim()) {
      u.searchParams.set("x-tenant-id", tenant.trim());
    }
    localStorage.setItem("tenant_id", tenant.trim());
    window.location.assign(u.toString());
  };

  const handleTenantChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.toLowerCase().replace(/\s/g, '');
    setTenant(value);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(username, password, tenant, keepSignedIn);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm font-medium leading-none">Username</label>
        <Input
          type="text"
          placeholder="Username or Email"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          disabled={isLoading}
        />
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium leading-none">Password</label>
        <PasswordInput
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          disabled={isLoading}
        />
      </div>

      {isMultiTenantEnabled && (
        <div className="space-y-2">
          <label className="text-sm font-medium leading-none">Tenant</label>
          <Input
            type="text"
            placeholder="Tenant ID"
            value={tenant}
            onChange={handleTenantChange}
            disabled={isLoading}
          />
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Checkbox
            id="keepSignedIn"
            checked={keepSignedIn}
            onCheckedChange={(checked) => setKeepSignedIn(checked as boolean)}
            disabled={isLoading}
          />
          <label
            htmlFor="keepSignedIn"
            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
          >
            Keep me signed in
          </label>
        </div>
        <Link
          to="/forgot-password"
          className="text-sm text-zinc-500 hover:text-zinc-600"
        >
          Forgot password?
        </Link>
      </div>

      <Button
        type="submit"
        className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
        disabled={isLoading || !username || !password}
      >
        {isLoading ? "Signing in..." : "Sign in"}
      </Button>

      {microsoftSsoEnabled && (
        <>
          <div className="relative py-2">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-zinc-200" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-white px-2 text-zinc-500">Or</span>
            </div>
          </div>
          <Button
            type="button"
            variant="outline"
            className="w-full border-zinc-300"
            disabled={isLoading}
            onClick={() => void handleMicrosoftSignIn()}
          >
            Sign in with Microsoft Entra ID
          </Button>
        </>
      )}
    </form>
  );
};
