import { useState } from "react";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Checkbox } from "@/components/checkbox";
import { Link } from "react-router-dom";
import { PasswordInput } from "@/components/PasswordInput";

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
        className="w-full bg-black text-white hover:bg-black/90"
        disabled={isLoading || !username || !password}
      >
        {isLoading ? "Signing in..." : "Sign in"}
      </Button>
    </form>
  );
};
