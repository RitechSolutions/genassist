import { useEffect, useState } from "react";
import { getAuthMe } from "@/services/auth";
import { getUser } from "@/services/users";
import { createApiKey, updateApiKey } from "@/services/apiKeys";
import { toast } from "react-hot-toast";
import { Role } from "@/interfaces/role.interface";
import { ApiKey } from "@/interfaces/api-key.interface";
import { presetToExpiresInDays } from "@/components/api-keys/apiKeyExpiryPresets";

const PRESET_DAY_VALUES = new Set([30, 90, 180, 365]);

function inferPresetFromApiKey(apiKey: ApiKey): string {
  if (typeof apiKey.credential_expiry_days === "number") {
    if (apiKey.credential_expiry_days <= 0) return "never";
    return String(apiKey.credential_expiry_days);
  }

  // Legacy fallback: try to infer from created_at -> credential_expires_at (if present).
  if (apiKey.created_at && apiKey.credential_expires_at) {
    const createdMs = new Date(apiKey.created_at).getTime();
    const expMs = new Date(apiKey.credential_expires_at).getTime();
    if (!Number.isNaN(createdMs) && !Number.isNaN(expMs) && expMs > createdMs) {
      const days = Math.round((expMs - createdMs) / (24 * 60 * 60 * 1000));
      if (PRESET_DAY_VALUES.has(days)) return String(days);
    }
  }

  return "never";
}

export function ApiKeyDialogLogic({
  isOpen,
  mode = "create",
  apiKeyToEdit = null,
  onApiKeyCreated,
  onApiKeyUpdated,
  onOpenChange,
}: {
  isOpen: boolean;
  mode?: "create" | "edit";
  apiKeyToEdit?: ApiKey | null;
  onApiKeyCreated?: () => void;
  onApiKeyUpdated?: (apiKey: ApiKey) => void;
  onOpenChange: (isOpen: boolean) => void;
}) {
  const [name, setName] = useState("");
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [isActive, setIsActive] = useState(true);
  const [availableRoles, setAvailableRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(false);
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [isKeyVisible, setIsKeyVisible] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">(mode);
  const [userId, setUserId] = useState<string | null>(null);
  const [hasGeneratedKey, setHasGeneratedKey] = useState(false);
  const [expiryPreset, setExpiryPreset] = useState<string>("never");

  useEffect(() => {
    const fetchUserData = async () => {
      try {
        const me = await getAuthMe();
        setUserId(me.id);

        const fullUser = await getUser(me.id);
        setAvailableRoles(fullUser.roles || []);

        if (mode === "edit" && apiKeyToEdit) {
          setDialogMode("edit");
          setName(apiKeyToEdit.name || "");
          setIsActive(apiKeyToEdit.is_active === 1);
          setSelectedRoles(
            apiKeyToEdit.roles?.map((r) => r.id) || apiKeyToEdit.role_ids || []
          );
          setGeneratedKey(apiKeyToEdit.key_val);
          setHasGeneratedKey(true);
          setExpiryPreset(inferPresetFromApiKey(apiKeyToEdit));
        } else {
          setDialogMode("create");
          setName("");
          setIsActive(true);
          setSelectedRoles([]);
          setHasGeneratedKey(false);
          setGeneratedKey(null);
          setExpiryPreset("never");
        }
      } catch (error) {
        toast.error("Failed to fetch user information.");
      } finally {
        setLoading(false);
      }
    };

    if (isOpen) {
      setLoading(true);
      fetchUserData();
    } else {
      resetForm();
    }
  }, [isOpen, mode, apiKeyToEdit]);

  const resetForm = () => {
    setName("");
    setSelectedRoles([]);
    setIsActive(true);
    setGeneratedKey(null);
    setIsKeyVisible(false);
    setDialogMode(mode);
    setAvailableRoles([]);
    setUserId(null);
    setHasGeneratedKey(false);
    setExpiryPreset("never");
  };

  const toggleRole = (roleId: string) => {
    setSelectedRoles((prev) =>
      prev.includes(roleId)
        ? prev.filter((id) => id !== roleId)
        : [...prev, roleId]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      toast.error("Name is required.");
      return;
    }

    try {
      setLoading(true);
      if (dialogMode === "create" && userId && !hasGeneratedKey) {
        const expiresInDays = presetToExpiresInDays(expiryPreset);
        const result = await createApiKey({
          name,
          user_id: userId,
          role_ids: selectedRoles,
          is_active: isActive ? 1 : 0,
          ...(expiresInDays !== undefined ? { expires_in_days: expiresInDays } : {}),
        });
        setGeneratedKey(result.key_val);
        setHasGeneratedKey(true);
        toast.success("API key created successfully.");

        if (onApiKeyCreated) {
          onApiKeyCreated();
        }
      } else if (dialogMode === "edit" && apiKeyToEdit && userId) {
        const commonFields = {
          name,
          user_id: userId,
          is_active: isActive ? 1 : 0,
        };

        const updateData: Partial<ApiKey> & { role_ids?: string[] } = {
          ...commonFields,
          role_ids: selectedRoles,
        };

        const expiresInDays = presetToExpiresInDays(expiryPreset);
        // Persist the user's selection on the record.
        // - undefined => "never" => backend expects 0 to clear/store Never
        // - number => set/store that many days
        updateData.expires_in_days = expiresInDays ?? 0;

        const updatedFromApi = await updateApiKey(apiKeyToEdit.id, updateData);
        toast.success("API key updated successfully.");

        if (onApiKeyUpdated) {
          onApiKeyUpdated(updatedFromApi);
        }

        onOpenChange(false);
      }
    } catch (error: unknown) {
      const err = error as { response?: { data?: Record<string, unknown> } };
      const data = err.response?.data;
      let errorMessage = "";

      if (data?.error) {
        errorMessage = String(data.error);
      } else if (data?.detail && typeof data.detail === "object") {
        const d0 = (data.detail as Record<string, { msg?: string }>)["0"];
        errorMessage = d0?.msg ?? "";
      }

      toast.error(
        `Failed to ${dialogMode} API key${
          errorMessage ? `: ${errorMessage}` : "."
        }`
      );
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = () => {
    if (generatedKey) {
      navigator.clipboard.writeText(generatedKey);
      toast.success("API key copied to clipboard.");
    }
  };

  const toggleKeyVisibility = () => {
    setIsKeyVisible(!isKeyVisible);
  };

  return {
    name,
    setName,
    selectedRoles,
    setSelectedRoles,
    isActive,
    setIsActive,
    availableRoles,
    loading,
    generatedKey,
    setGeneratedKey,
    isKeyVisible,
    toggleKeyVisibility,
    hasGeneratedKey,
    setHasGeneratedKey,
    dialogMode,
    setDialogMode,
    userId,
    toggleRole,
    handleSubmit,
    copyToClipboard,
    expiryPreset,
    setExpiryPreset,
  };
}
