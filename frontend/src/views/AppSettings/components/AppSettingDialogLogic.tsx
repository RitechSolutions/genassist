import { useEffect, useState } from "react";
import { createAppSetting, updateAppSetting } from "@/services/appSettings";
import { toast } from "react-hot-toast";
import { AppSetting } from "@/interfaces/app-setting.interface";

export function AppSettingDialogLogic({
  isOpen,
  mode = "create",
  settingToEdit = null,
  onSettingCreated,
  onOpenChange
}: {
  isOpen: boolean;
  mode?: "create" | "edit";
  settingToEdit?: AppSetting | null;
  onSettingCreated?: () => void;
  onOpenChange: (isOpen: boolean) => void;
}) {
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [description, setDescription] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isEncrypted, setIsEncrypted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      if (mode === "edit" && settingToEdit) {
        setKey(settingToEdit.key || "");
        setValue(settingToEdit.value || "");
        setDescription(settingToEdit.description || "");
        setIsActive(settingToEdit.is_active === 1);
        setIsEncrypted(settingToEdit.encrypted === 1);
      } else {
        // Reset form for create mode
        setKey("");
        setValue("");
        setDescription("");
        setIsActive(true);
        setIsEncrypted(false);
      }
    }
  }, [isOpen, mode, settingToEdit]);

  const handleSubmit = async () => {
    // Validate form
    if (!key.trim()) {
      toast.error("Key is required");
      return;
    }

    if (!value.trim()) {
      toast.error("Value is required");
      return;
    }

    if (!description.trim()) {
      toast.error("Description is required");
      return;
    }

    try {
      setIsSubmitting(true);

      const settingData: Partial<AppSetting> = {
        key: key.trim(),
        value: value.trim(),
        description: description.trim(),
        is_active: isActive ? 1 : 0,
        encrypted: isEncrypted ? 1 : 0
      };

      if (mode === "create") {
        await createAppSetting(settingData);
        toast.success("Setting created successfully");
      } else if (mode === "edit" && settingToEdit) {
        await updateAppSetting(settingToEdit.id, settingData);
        toast.success("Setting updated successfully");
      }

      if (onSettingCreated) {
        onSettingCreated();
      }
      
      onOpenChange(false);
    } catch (error) {
      toast.error(`Failed to ${mode === "create" ? "create" : "update"} setting`);
      console.error(error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return {
    key,
    setKey,
    value,
    setValue,
    description,
    setDescription,
    isActive,
    setIsActive,
    isEncrypted,
    setIsEncrypted,
    isSubmitting,
    handleSubmit
  };
} 