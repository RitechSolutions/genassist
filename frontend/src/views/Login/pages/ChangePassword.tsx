import { Button } from "@/components/button";
import { Card } from "@/components/card";
import { Input } from "@/components/input";
import { PasswordInput } from "@/components/PasswordInput";
import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { toast } from "react-hot-toast";
import { apiRequest } from "@/config/api";
import {
  isPasswordUpdateRequired,
  getAccessToken,
  logout,
  getAuthMe,
} from "@/services/auth";

export default function ChangePassword() {
  const [username, setUsername] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
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
      }
    };

    if (token) {
      fetchUser();
    }
  }, [navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!currentPassword) {
      toast.error("Current password is required.");
      return;
    }

    if (!newPassword) {
      toast.error("New password is required.");
      return;
    }

    if (newPassword !== confirmPassword) {
      toast.error("Passwords do not match.");
      return;
    }

    if (newPassword === currentPassword) {
      toast.error("The new password must be different from the current one.");
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
          toast.error("Current password is incorrect.");
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

  return (
    <div className="min-h-screen bg-zinc-50/90 flex flex-col">
      <div className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between space-y-2">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">
              {isForced ? "Password Update Required" : "Change Password"}
            </h2>
            {isForced && (
              <p className="text-sm text-muted-foreground mt-2">
                Your password needs to be updated before you can continue using
                the application.
              </p>
            )}
          </div>
        </div>
        <Card className="max-w-md mx-auto mt-8">
          <form onSubmit={handleSubmit} className="space-y-4 p-6">
            <div className="space-y-2">
              <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                Username
              </label>
              <Input
                type="text"
                value={username}
                disabled
                placeholder="Loading username..."
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                Current Password
              </label>
              <PasswordInput
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter your current password"
                required
                disabled={isSubmitting}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                New Password
              </label>
              <PasswordInput
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter your new password"
                required
                disabled={isSubmitting}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                Confirm New Password
              </label>
              <PasswordInput
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm your new password"
                required
                disabled={isSubmitting}
              />
            </div>
            <div className="flex justify-end space-x-2 mt-6">
              {!isForced && (
                <Button
                  variant="outline"
                  type="button"
                  onClick={() => navigate(-1)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
              )}
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Updating..." : "Update Password"}
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
