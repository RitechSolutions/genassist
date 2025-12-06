import { useEffect, useState } from "react";
import { getAuthMe } from "@/services/auth";
import { getUser } from "@/services/users";
import { createApiKey, updateApiKey } from "@/services/apiKeys";
import { toast } from "react-hot-toast";
import { Role } from "@/interfaces/role.interface";
import { ApiKey } from "@/interfaces/api-key.interface";

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
        } else {
          setDialogMode("create");
          setName("");
          setIsActive(true);
          setSelectedRoles([]);
          setHasGeneratedKey(false);
          setGeneratedKey(null);
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
        const result = await createApiKey({
          name,
          user_id: userId,
          role_ids: selectedRoles,
          is_active: isActive ? 1 : 0,
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

        await updateApiKey(apiKeyToEdit.id, updateData);
        toast.success("API key updated successfully.");

        if (onApiKeyUpdated) {
          const updatedKey: ApiKey = {
            ...apiKeyToEdit,
            ...commonFields,
            roles: availableRoles.filter((role) =>
              selectedRoles.includes(role.id)
            ),
          };
          onApiKeyUpdated(updatedKey);
        }

        onOpenChange(false);
      }
    } catch (error) {
      const data = error.response.data;
      let errorMessage = "";

      if (data.error) {
        errorMessage = data.error;
      } else if (data.detail) {
        errorMessage = data.detail["0"].msg;
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
  };
}
