import { useEffect, useState } from "react";
import { getAuthMe } from "@/services/auth";
import { getUser } from "@/services/users";
import { toast } from "react-hot-toast";
import { Role } from "@/interfaces/role.interface";
import { ApiKey } from "@/interfaces/api-key.interface";

/**
 * Non-form state for the API key dialog: the authenticated user, the roles
 * available to assign, and the one-time "generated key" reveal state. The form
 * fields themselves (name, active, roles, expiry) are owned by CRUDDialog.
 */
export function useApiKeyDialogState({
  isOpen,
  mode = "create",
  apiKeyToEdit = null,
}: {
  isOpen: boolean;
  mode?: "create" | "edit";
  apiKeyToEdit?: ApiKey | null;
}) {
  const [userId, setUserId] = useState<string | null>(null);
  const [availableRoles, setAvailableRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(false);
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [isKeyVisible, setIsKeyVisible] = useState(false);
  const [hasGeneratedKey, setHasGeneratedKey] = useState(false);

  useEffect(() => {
    const fetchUserData = async () => {
      try {
        const me = await getAuthMe();
        setUserId(me.id ?? null);

        const fullUser = await getUser(me.id);
        setAvailableRoles(fullUser?.roles || []);

        // A freshly opened dialog never starts on the reveal screen.
        setGeneratedKey(null);
        setHasGeneratedKey(false);
        setIsKeyVisible(false);
      } catch {
        toast.error("Failed to fetch user information.");
      } finally {
        setLoading(false);
      }
    };

    if (isOpen) {
      setLoading(true);
      fetchUserData();
    } else {
      resetState();
    }
  }, [isOpen, mode, apiKeyToEdit]);

  const resetState = () => {
    setUserId(null);
    setAvailableRoles([]);
    setGeneratedKey(null);
    setIsKeyVisible(false);
    setHasGeneratedKey(false);
  };

  const toggleKeyVisibility = () => setIsKeyVisible((prev) => !prev);

  const copyToClipboard = () => {
    if (generatedKey) {
      navigator.clipboard.writeText(generatedKey);
      toast.success("API key copied to clipboard.");
    }
  };

  return {
    userId,
    availableRoles,
    loading,
    generatedKey,
    setGeneratedKey,
    isKeyVisible,
    toggleKeyVisibility,
    hasGeneratedKey,
    setHasGeneratedKey,
    copyToClipboard,
  };
}
