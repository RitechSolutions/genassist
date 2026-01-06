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
import { Eye, EyeOff, Copy } from "lucide-react";
import { ApiKeyDialogLogic } from "./ApiKeyDialogLogic";
import { ApiKey } from "@/interfaces/api-key.interface";
import { ApiRoleSelection } from "./ApiRoleSelection";
import { Switch } from "@/components/switch";
import { maskInput } from "@/helpers/utils";

interface ApiKeyDialogProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  onApiKeyCreated?: () => void;
  onApiKeyUpdated?: (apiKey: ApiKey) => void;
  mode?: "create" | "edit";
  apiKeyToEdit?: ApiKey | null;
}

export function ApiKeyDialog({
  isOpen,
  onOpenChange,
  onApiKeyCreated,
  onApiKeyUpdated,
  mode = "create",
  apiKeyToEdit = null,
}: ApiKeyDialogProps) {
  const {
    name,
    setName,
    selectedRoles,
    setSelectedRoles,
    isActive,
    setIsActive,
    availableRoles,
    loading,
    generatedKey,
    isKeyVisible,
    toggleKeyVisibility,
    hasGeneratedKey,
    toggleRole,
    handleSubmit,
    copyToClipboard,
    dialogMode,
  } = ApiKeyDialogLogic({
    isOpen,
    mode,
    apiKeyToEdit,
    onApiKeyCreated,
    onApiKeyUpdated,
    onOpenChange,
  });

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] p-0 overflow-hidden">
        <form
          onSubmit={handleSubmit}
          className="max-h-[90vh] overflow-y-auto overflow-x-hidden flex flex-col"
        >
          <DialogHeader className="p-6 pb-4">
            <DialogTitle>
              {mode === "create" ? "Generate New API Key" : "Edit API Key"}
            </DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 px-6 pb-6">
            <div className="flex justify-between items-center">
              <Label htmlFor="name">Name</Label>
            </div>
            <Input
              id="name"
              placeholder="API Key Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={loading}
            />

            <ApiRoleSelection
              availableRoles={availableRoles}
              selectedRoles={selectedRoles}
              toggleRole={toggleRole}
              isLoading={loading}
            />

            <div className="flex items-center gap-2">
              <Label htmlFor="is_active">Active</Label>
              <Switch
                id="is_active"
                checked={isActive}
                onCheckedChange={setIsActive}
              />
            </div>

            {hasGeneratedKey && generatedKey && (
              <div className="space-y-2 mt-4">
                <Label htmlFor="generated_key">Generated API Key</Label>
                <div className="relative flex flex-row items-center">
                  <Input
                    id="generated_key"
                    value={
                      isKeyVisible
                        ? generatedKey
                        : maskInput(generatedKey || "")
                    }
                    readOnly
                    className="w-full z-10"
                  />
                  <div className="absolute right-2 flex gap-1 elevation-1 z-20">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={toggleKeyVisibility}
                      title={isKeyVisible ? "Hide key" : "Show key"}
                    >
                      {isKeyVisible ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={copyToClipboard}
                      title="Copy to clipboard"
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  This API key will only be shown once. Make sure to copy and
                  store it securely.
                </p>
              </div>
            )}
          </div>

          <DialogFooter className="px-6 py-4 border-t">
            <div className="flex justify-end gap-3 w-full">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              {dialogMode === "create" && (
                <Button type="submit" disabled={loading || hasGeneratedKey}>
                  {loading ? "Generating..." : "Generate Key"}
                </Button>
              )}

              {dialogMode === "edit" && (
                <Button type="submit" disabled={loading || !hasGeneratedKey}>
                  {loading ? "Updating..." : "Update Key"}
                </Button>
              )}
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
