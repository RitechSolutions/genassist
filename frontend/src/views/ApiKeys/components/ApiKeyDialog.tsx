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

interface ApiKeyDialogProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  onApiKeyCreated?: () => void;
  mode?: "create" | "edit";
  apiKeyToEdit?: ApiKey | null;
}

export function ApiKeyDialog({
  isOpen,
  onOpenChange,
  onApiKeyCreated,
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
    onOpenChange,
  });

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "Generate New API Key" : "Edit API Key"}
          </DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? "Fill in the details below to generate a new API key for your account."
              : "Update the API key details below."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="flex justify-between items-center">
              <Label htmlFor="name">Name</Label>
            </div>
            <Input
              id="name"
              placeholder="API Key Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              disabled={loading}
            />

            <div className="flex items-center gap-2">
              <Label htmlFor="is_active">Active</Label>
              <Switch
                id="is_active"
                checked={isActive}
                onCheckedChange={setIsActive}
              />
            </div>

            <ApiRoleSelection
              availableRoles={availableRoles}
              selectedRoles={selectedRoles}
              toggleRole={toggleRole}
              isLoading={loading}
            />

            {hasGeneratedKey && generatedKey && (
              <div className="space-y-2 mt-4">
                <Label htmlFor="generated_key">Generated API Key</Label>
                <div className="relative">
                  <Input
                    id="generated_key"
                    value={
                      isKeyVisible
                        ? generatedKey
                        : generatedKey.replace(/./g, "*")
                    }
                    readOnly
                    className="pr-20"
                  />
                  <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-2">
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

          <DialogFooter>
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
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
