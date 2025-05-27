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
  onOpenChange
}: {
  isOpen: boolean;
  mode?: "create" | "edit";
  apiKeyToEdit?: ApiKey | null;
  onApiKeyCreated?: () => void;
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
          setSelectedRoles(apiKeyToEdit.roles?.map((r) => r.id) || apiKeyToEdit.role_ids || []);
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
        console.error("Failed to load user data:", error);
        toast.error("Failed to load user information.");
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
    setLoading(true);

    try {
      if (dialogMode === "create" && userId && !hasGeneratedKey) {
        const result = await createApiKey({
          name,
          user_id: userId,
          role_ids: selectedRoles,
          is_active: isActive ? 1 : 0,
        });
        setGeneratedKey(result.key_val);
        setHasGeneratedKey(true);
        toast.success("API Key created successfully");
      } else if (dialogMode === "edit" && apiKeyToEdit && userId) {
        const updateData: Partial<ApiKey> & { role_ids?: string[] } = {
          name,
          user_id: userId,
          is_active: isActive ? 1 : 0,
          role_ids: selectedRoles,
        };
        await updateApiKey(apiKeyToEdit.id, updateData);
        toast.success("API Key updated successfully");
        onOpenChange(false);
      }
      if (onApiKeyCreated) {
        onApiKeyCreated();
      }
    } catch (error) {
      console.error("Error creating/updating API key:", error);
      toast.error("You are unauthorized to perform this action.");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = () => {
    if (generatedKey) {
      navigator.clipboard.writeText(generatedKey);
      toast.success("API key has been copied to clipboard");
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
