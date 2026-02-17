import { Card } from "@/components/card";
import { CheckCircle, FolderCog, Save } from "lucide-react";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import type { FileManagerSettings } from "@/services/fileManager";
import { useState } from "react";
import { Button } from "@/components/button";
import toast from "react-hot-toast";
import { updateFileManagerSettings } from "@/services/appSettings";

interface FileManagerSettingsCardProps {
  settings: FileManagerSettings;
}

const providerOptions = [
  { value: "local", label: "Local", disabled: false },
  { value: "s3", label: "S3", disabled: false },
  { value: "azure", label: "Azure", disabled: true },
  { value: "sharepoint", label: "SharePoint", disabled: true },
  { value: "gcs", label: "GCS", disabled: true },
];

export const FileManagerSettingsCard = ({ settings }: FileManagerSettingsCardProps) => {
  const provider = settings.file_manager_provider || "local";
  const [selectedProvider, setSelectedProvider] = useState(provider);
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    try {
      setIsSaving(true);
      await updateFileManagerSettings({
        file_manager_enabled: settings.file_manager_enabled,
        file_manager_provider: selectedProvider,
        base_path: selectedProvider === "local" ? settings.base_path : undefined,
        aws_bucket_name: selectedProvider === "s3" ? settings.aws_bucket_name : undefined,
      });

      toast.success("File manager settings saved", {
        icon: <FolderCog className="w-5 h-5 sm:w-6 sm:h-6 text-green-500" />,
        duration: 3000,
      });
    } catch (error) {
      toast.error("Failed to update file manager settings", {
        icon: <FolderCog className="w-5 h-5 sm:w-6 sm:h-6 text-red-500" />,
        duration: 3000,
      });
      throw new Error("Failed to update file manager settings");
    } finally {
      setIsSaving(false);
    }
    setIsSaving(true);

    toast.success("File manager settings saved", {
      icon: <FolderCog className="w-5 h-5 sm:w-6 sm:h-6 text-green-500" />,
      duration: 3000,
    });

    setTimeout(() => {
      setIsSaving(false);
    }, 3000);
  };

  return (
    <Card className="p-4 sm:p-6 shadow-sm animate-fade-up bg-white">
      <div className="flex items-center gap-3 mb-4">
        <FolderCog className="w-5 h-5 sm:w-6 sm:h-6 text-primary" />
        <div>
          <h2 className="text-base sm:text-lg font-semibold">File Manager Settings</h2>
          <p className="text-xs sm:text-sm text-muted-foreground">
            Storage provider configuration
          </p>
        </div>

        <Button
          variant="outline"
          type="button"
          className="ml-auto rounded-full"
          loading={isSaving}
          icon={<Save className="w-4 h-4" />}
          onClick={handleSave}>
          Save
        </Button>
      </div>

      <div className="space-y-1">
        <div className="flex items-center justify-between h-[40px]">
          <label className="text-sm font-medium">Default Storage Provider</label>
          <Select value={selectedProvider} onValueChange={(value) => setSelectedProvider(value)}>
            <SelectTrigger className="w-1/2">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {providerOptions.map((opt) => (
                <SelectItem
                  key={opt.value}
                  value={opt.value}
                  disabled={opt.disabled}
                >
                  {opt.label}
                  {opt.disabled && (
                    <span className="ml-1 text-xs text-muted-foreground">(coming soon)</span>
                  )}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {selectedProvider === "local" && (
          <div className="flex items-center justify-between h-[40px]">
            <label className="text-sm font-medium">Base Path</label>
            <input
              type="text"
              value={settings.base_path || ""}
              readOnly
              className="w-1/2 rounded-full border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none disabled:opacity-75"
            />
          </div>
        )}

        {selectedProvider === "s3" && (
          <div className="flex items-center justify-between h-[40px]">
            <label className="text-sm font-medium">Bucket Name</label>
            <input
              type="text"
              value={settings.aws_bucket_name || ""}
              readOnly
              className="w-1/2 rounded-full border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none disabled:opacity-75"
            />
          </div>
        )}
      </div>
    </Card>
  );
};
