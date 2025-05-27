import { Button } from "@/components/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { Switch } from "@/components/switch";
import { Eye, EyeOff } from "lucide-react";
import { AppSettingDialogLogic } from "./AppSettingDialogLogic";
import { AppSetting } from "@/interfaces/app-setting.interface";

interface AppSettingDialogProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  onSettingCreated?: () => void;
  mode?: "create" | "edit";
  settingToEdit?: AppSetting | null;
}

export function AppSettingDialog({
  isOpen,
  onOpenChange,
  onSettingCreated,
  mode = "create",
  settingToEdit,
}: AppSettingDialogProps) {
  const {
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
    handleSubmit,
  } = AppSettingDialogLogic({
    isOpen,
    onOpenChange,
    mode,
    settingToEdit,
    onSettingCreated,
  });

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{mode === "create" ? "Add New Setting" : "Edit Setting"}</DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? "Configure a new application setting"
              : "Update the application setting details"}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="key">Setting Key</Label>
            <Input
              id="key"
              placeholder="Enter a unique setting key"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              disabled={mode === "edit"}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="value">Value</Label>
            <Input
              id="value"
              placeholder="Enter the setting value"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              type={isEncrypted ? "password" : "text"}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              placeholder="Describe what this setting is used for"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="is-active"
              checked={isActive}
              onCheckedChange={setIsActive}
            />
            <Label htmlFor="is-active">Active</Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="encrypted"
              checked={isEncrypted}
              onCheckedChange={setIsEncrypted}
            />
            <Label htmlFor="encrypted" className="flex items-center gap-2">
              Encrypted
              {isEncrypted ? (
                <Eye className="w-4 h-4 text-gray-500" />
              ) : (
                <EyeOff className="w-4 h-4 text-gray-400" />
              )}
            </Label>
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting
              ? "Saving..."
              : mode === "create"
              ? "Create Setting"
              : "Update Setting"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
} 