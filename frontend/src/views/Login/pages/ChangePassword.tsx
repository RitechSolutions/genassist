import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { toast } from "react-hot-toast";
import { ArrowLeft, Check, ShieldAlert } from "lucide-react";

import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { Skeleton } from "@/components/skeleton";
import { PasswordInput } from "@/components/PasswordInput";
import { GenAssistLogo } from "@/components/GenAssistLogo";
import { cn } from "@/helpers/utils";
import { apiRequest } from "@/config/api";
import {
  isPasswordUpdateRequired,
  getAccessToken,
  logout,
  getAuthMe,
} from "@/services/auth";

type FieldName = "currentPassword" | "newPassword" | "confirmPassword";
type FieldErrors = Partial<Record<FieldName, string>>;

const STRENGTH_LEVELS = [
  { label: "Weak", bar: "bg-destructive", text: "text-destructive" },
  { label: "Fair", bar: "bg-amber-500", text: "text-amber-600 dark:text-amber-500" },
  { label: "Good", bar: "bg-blue-500", text: "text-blue-600 dark:text-blue-400" },
  { label: "Strong", bar: "bg-green-500", text: "text-green-600 dark:text-green-500" },
];

/**
 * Advisory strength hint only — the API enforces no password policy, so this
 * never blocks submission. One point each for length, extra length, mixed
 * case, digits and symbols, collapsed onto the four levels above.
 */
const getStrengthLevel = (password: string) => {
  let score = 0;
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 1;
  if (/\d/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;

  if (score <= 1) return 0;
  if (score === 2) return 1;
  if (score === 3) return 2;
  return 3;
};

export default function ChangePassword() {
  const [username, setUsername] = useState("");
  const [isLoadingUser, setIsLoadingUser] = useState(true);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isForced, setIsForced] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Check if this is a forced password update
    const forcedUpdate = isPasswordUpdateRequired();
    setIsForced(forcedUpdate);

    const token = getAccessToken();

    if (!forcedUpdate && !token) {
      // If not forced and not authenticated, redirect to login
      navigate("/login");
      return;
    }

    // Fetch current user
    const fetchUser = async () => {
      try {
        const me = await getAuthMe();
        if (me?.username) {
          setUsername(me.username);
        }
      } catch (error) {
        // ignore
      } finally {
        setIsLoadingUser(false);
      }
    };

    if (token) {
      fetchUser();
    } else {
      setIsLoadingUser(false);
    }
  }, [navigate]);

  const clearError = (field: FieldName) =>
    setErrors((prev) => (prev[field] ? { ...prev, [field]: undefined } : prev));

  const handleSignOut = () => {
    logout();
    navigate("/login");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const nextErrors: FieldErrors = {};

    if (!currentPassword) {
      nextErrors.currentPassword = "Current password is required.";
    }

    if (!newPassword) {
      nextErrors.newPassword = "New password is required.";
    } else if (newPassword === currentPassword) {
      nextErrors.newPassword =
        "The new password must be different from the current one.";
    }

    if (newPassword !== confirmPassword) {
      nextErrors.confirmPassword = "Passwords do not match.";
    }

    setErrors(nextErrors);

    if (Object.keys(nextErrors).length > 0) {
      return;
    }

    setIsSubmitting(true);

    try {
      const token = getAccessToken();

      if (!token) {
        toast.error("Authentication token not found. Please log in again.");
        navigate("/login");
        return;
      }

      await apiRequest(
        "POST",
        "auth/change-password",
        {
          username,
          old_password: currentPassword,
          new_password: newPassword,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      toast.success("Password updated successfully.");

      // Clear all authentication data to force fresh login
      logout();

      // Navigate to login page
      navigate("/login", {
        state: {
          message:
            "Password updated successfully. Please log in with your new password.",
          from: location.state?.from,
        },
      });
    } catch (error) {
      if (error && typeof error === "object" && "response" in error) {
        const axiosError = error as {
          response?: {
            status?: number;
            data?: { detail?: string; message?: string };
          };
        };

        if (axiosError.response?.status === 401) {
          setErrors({ currentPassword: "Current password is incorrect." });
        } else if (axiosError.response?.data?.detail) {
          toast.error(axiosError.response.data.detail);
        } else if (axiosError.response?.data?.message) {
          toast.error(axiosError.response.data.message);
        } else {
          toast.error("Failed to update password.");
        }
      } else {
        toast.error("Failed to update password.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const strength = getStrengthLevel(newPassword);
  const strengthLevel = STRENGTH_LEVELS[strength];
  const passwordsMatch =
    confirmPassword.length > 0 && newPassword === confirmPassword;

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-md space-y-6">
        <div className="space-y-2">
          <GenAssistLogo
            width={200}
            height={52}
            className="text-zinc-900 dark:text-zinc-100"
          />

          <h1 className="text-3xl font-bold tracking-tight">
            {isForced ? "Update your password" : "Change password"}
          </h1>
          <p className="text-muted-foreground">
            {isForced
              ? "Your password needs to be updated before you can continue."
              : "Choose a new password for your account. You'll be asked to sign in again once it's updated."}
          </p>
        </div>

        {isForced && (
          <div
            role="alert"
            className="flex items-start gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-4"
          >
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
            <div className="space-y-1">
              <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
                Password update required
              </p>
              <p className="text-sm text-amber-900/80 dark:text-amber-200/80">
                For security reasons your current password has expired. Set a
                new one to regain access.
              </p>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3 rounded-full border border-border bg-muted/40 px-3 py-2">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold uppercase text-primary">
            {username.charAt(0) || "?"}
          </span>
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">Signed in as</p>
            {isLoadingUser ? (
              <Skeleton className="mt-1 h-4 w-32" />
            ) : (
              <p className="truncate text-sm font-medium">
                {username || "Unknown account"}
              </p>
            )}
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="current-password">Current password</Label>
            <PasswordInput
              id="current-password"
              value={currentPassword}
              onChange={(e) => {
                setCurrentPassword(e.target.value);
                clearError("currentPassword");
              }}
              placeholder="Enter your current password"
              autoComplete="current-password"
              aria-invalid={Boolean(errors.currentPassword)}
              disabled={isSubmitting}
            />
            {errors.currentPassword && (
              <p className="text-xs text-destructive">
                {errors.currentPassword}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="new-password">New password</Label>
            <PasswordInput
              id="new-password"
              value={newPassword}
              onChange={(e) => {
                setNewPassword(e.target.value);
                clearError("newPassword");
              }}
              placeholder="Enter your new password"
              autoComplete="new-password"
              aria-invalid={Boolean(errors.newPassword)}
              disabled={isSubmitting}
            />
            {newPassword && (
              <div className="flex items-center gap-2">
                <div className="flex flex-1 gap-1">
                  {STRENGTH_LEVELS.map((level, index) => (
                    <span
                      key={level.label}
                      className={cn(
                        "h-1 flex-1 rounded-full transition-colors",
                        index <= strength ? strengthLevel.bar : "bg-muted"
                      )}
                    />
                  ))}
                </div>
                <span className={cn("text-xs font-medium", strengthLevel.text)}>
                  {strengthLevel.label}
                </span>
              </div>
            )}
            {errors.newPassword && (
              <p className="text-xs text-destructive">{errors.newPassword}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirm-password">Confirm new password</Label>
            <PasswordInput
              id="confirm-password"
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                clearError("confirmPassword");
              }}
              placeholder="Re-enter your new password"
              autoComplete="new-password"
              aria-invalid={Boolean(errors.confirmPassword)}
              disabled={isSubmitting}
            />
            {errors.confirmPassword ? (
              <p className="text-xs text-destructive">
                {errors.confirmPassword}
              </p>
            ) : (
              passwordsMatch && (
                <p className="flex items-center gap-1 text-xs text-green-600 dark:text-green-500">
                  <Check className="h-3.5 w-3.5" />
                  Passwords match
                </p>
              )
            )}
          </div>

          <Button
            type="submit"
            className="w-full"
            loading={isSubmitting}
            disabled={
              isSubmitting ||
              !currentPassword ||
              !newPassword ||
              !confirmPassword
            }
          >
            {isSubmitting ? "Updating..." : "Update password"}
          </Button>

          {!isForced && (
            <Button
              variant="ghost"
              type="button"
              className="w-full"
              icon={<ArrowLeft className="h-4 w-4" />}
              onClick={() => navigate(-1)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
          )}
        </form>

        {isForced && (
          <div className="text-center text-sm">
            <span className="text-muted-foreground">Not your account? </span>
            <button
              type="button"
              onClick={handleSignOut}
              disabled={isSubmitting}
              className="font-medium text-foreground hover:underline disabled:opacity-50"
            >
              Sign in as someone else
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
