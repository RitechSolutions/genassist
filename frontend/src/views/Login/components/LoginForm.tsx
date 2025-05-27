import { useState } from "react";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Checkbox } from "@/components/checkbox";
import { Link } from "react-router-dom";

interface LoginFormProps {
  onSubmit: (username: string, password: string, keepSignedIn: boolean) => void;
  isLoading: boolean;
}

export const LoginForm = ({ onSubmit, isLoading }: LoginFormProps) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [keepSignedIn, setKeepSignedIn] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(username, password, keepSignedIn);
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
        <label className="text-sm font-medium leading-none">
          Password
        </label>
        <Input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          disabled={isLoading}
        />
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Checkbox
            id="keepSignedIn"
            checked={keepSignedIn}
            onCheckedChange={(checked) =>
              setKeepSignedIn(checked as boolean)
            }
            disabled={isLoading}
          />
          <label
            htmlFor="keepSignedIn"
            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
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