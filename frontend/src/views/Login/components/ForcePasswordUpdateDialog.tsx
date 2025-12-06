import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/dialog";
import { Label } from "@/components/label";
import { Input } from "@/components/input";
import { Button } from "@/components/button";
import { toast } from "react-hot-toast";
import { apiRequest } from "@/config/api";
import { PasswordInput } from "@/components/PasswordInput";
import { logout } from "@/services/auth";

interface ForcePasswordUpdateDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  username: string;
  oldPassword: string;
  token: string;
  onPasswordUpdated: () => void;
}

export function ForcePasswordUpdateDialog({
  isOpen,
  onOpenChange,
  username,
  oldPassword,
  token,
  onPasswordUpdated,
}: ForcePasswordUpdateDialogProps) {
  const [newPassword, setNewPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!newPassword) {
      toast.error("New password is required.");
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await apiRequest(
        "POST",
        "auth/change-password",
        {
          username,
          old_password: oldPassword,
          new_password: newPassword,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      toast.success("Password updated successfully. Please log in again.");
      // clear authentication state
      logout();

      onPasswordUpdated();
      onOpenChange(false);
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
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Update Your Password</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label>Username</Label>
            <Input value={username} readOnly />
          </div>
          <div>
            <Label>Old Password</Label>
            <PasswordInput value={oldPassword} readOnly />
          </div>
          <div>
            <Label>New Password</Label>
            <PasswordInput
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Enter your new password"
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Updating..." : "Update Password"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
