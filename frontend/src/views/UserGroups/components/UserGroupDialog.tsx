import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Button } from "@/components/button";
import { Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";
import { UserGroup } from "@/interfaces/userGroup.interface";
import { createUserGroup, updateUserGroup } from "@/services/userGroups";

interface UserGroupDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onGroupSaved: () => void;
  onGroupUpdated?: (group: UserGroup) => void;
  groupToEdit?: UserGroup | null;
  mode?: "create" | "edit";
}

export function UserGroupDialog({
  isOpen,
  onOpenChange,
  onGroupSaved,
  onGroupUpdated,
  groupToEdit = null,
  mode = "create",
}: UserGroupDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">(mode);

  useEffect(() => {
    setDialogMode(mode);
  }, [mode]);

  useEffect(() => {
    if (isOpen) {
      if (groupToEdit && mode === "edit") {
        setName(groupToEdit.name);
        setDescription(groupToEdit.description ?? "");
      } else {
        setName("");
        setDescription("");
      }
    }
  }, [isOpen, groupToEdit, mode]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      toast.error("Name is required.");
      return;
    }

    try {
      setIsSubmitting(true);
      const payload: Partial<UserGroup> = {
        name: name.trim(),
        description: description.trim() || null,
      };

      if (dialogMode === "create") {
        await createUserGroup(payload);
        toast.success("User group created successfully.");
        onGroupSaved();
      } else {
        if (!groupToEdit?.id) return;
        const updated = await updateUserGroup(groupToEdit.id, payload);
        toast.success("User group updated successfully.");
        onGroupUpdated?.(updated);
      }

      onOpenChange(false);
    } catch (err: any) {
      const data = err?.response?.data;
      const errorMessage = data?.error ?? data?.detail ?? null;
      toast.error(
        `Failed to ${dialogMode === "create" ? "create" : "update"} user group${errorMessage ? `: ${errorMessage}` : "."}`
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const title = dialogMode === "create" ? "Create New User Group" : "Edit User Group";
  const submitButtonText = dialogMode === "create" ? "Create Group" : "Update Group";
  const loadingText = dialogMode === "create" ? "Creating..." : "Updating...";

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px] p-0 overflow-hidden">
        <form onSubmit={handleSubmit}>
          <DialogHeader className="p-6 pb-4">
            <DialogTitle className="text-xl">{title}</DialogTitle>
          </DialogHeader>

          <div className="px-6 pb-6 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter group name"
                autoFocus
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Enter description (optional)"
              />
            </div>
          </div>

          <DialogFooter className="px-6 py-4 border-t">
            <div className="flex justify-end gap-3 w-full">
              <Button
                type="button"
                variant="outline"
                className="px-4"
                onClick={() => onOpenChange(false)}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting} className="px-4">
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {loadingText}
                  </>
                ) : (
                  submitButtonText
                )}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}