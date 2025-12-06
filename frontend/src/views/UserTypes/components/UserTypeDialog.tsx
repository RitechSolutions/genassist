import { useEffect, useState } from "react";
import { UserType } from "@/interfaces/userType.interface";
import { toast } from "react-hot-toast";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/dialog";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { updateUserType, createUserType } from "@/services/userTypes";
import { Button } from "@/components/button";
import { Loader2 } from "lucide-react";

interface UserTypeDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onUserTypeSaved: () => void;
  onUserTypeUpdated?: (userType: UserType) => void;
  userTypeToEdit?: UserType | null;
  mode?: "create" | "edit";
}

export function UserTypeDialog({
  isOpen,
  onOpenChange,
  onUserTypeSaved,
  onUserTypeUpdated,
  userTypeToEdit = null,
  mode = "create",
}: UserTypeDialogProps) {
  const [name, setName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [userTypeId, setUserTypeId] = useState<string | undefined>(undefined);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">(mode);

  const title =
    dialogMode === "create" ? "Create New User Type" : "Edit User Type";
  const submitButtonText =
    dialogMode === "create" ? "Create User Type" : "Update User Type";
  const loadingText = dialogMode === "create" ? "Creating..." : "Updating...";

  useEffect(() => {
    setDialogMode(mode);
  }, [mode]);

  useEffect(() => {
    if (isOpen) {
      resetForm();

      if (userTypeToEdit && dialogMode === "edit") {
        populateFormWithUserTypeData(userTypeToEdit);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, userTypeToEdit, dialogMode]);

  const populateFormWithUserTypeData = (userType: UserType) => {
    setUserTypeId(userType.id);
    setName(userType.name || "");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      toast.error("Name is required.");
      return;
    }

    try {
      setIsSubmitting(true);
      const userTypeData: Partial<UserType> = {
        name: name.trim(),
      };

      if (dialogMode === "create") {
        await createUserType(userTypeData);
        toast.success("User type created successfully.");
        onUserTypeSaved();
      } else {
        if (!userTypeId) {
          toast.error("User type ID is required.");
          return;
        }
        await updateUserType(userTypeId, userTypeData);
        toast.success("User type updated successfully.");
        if (onUserTypeUpdated && userTypeToEdit) {
          const updatedUserType: UserType = {
            ...userTypeToEdit,
            ...userTypeData,
          };
          onUserTypeUpdated(updatedUserType);
        }
      }

      onOpenChange(false);
      resetForm();
    } catch (err) {
      const data = err.response.data;
      let errorMessage = "";

      if (err.status === 400) {
        errorMessage = "A user type with this name already exists.";
      } else if (data.error) {
        errorMessage = data.error;
      } else if (data.detail) {
        errorMessage = data.detail["0"].msg;
      }

      toast.error(
        `Failed to ${dialogMode} user type${
          errorMessage ? `: ${errorMessage}` : "."
        }`
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    if (dialogMode === "create") {
      setUserTypeId(undefined);
      setName("");
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[550px] p-0 overflow-hidden">
        <form
          onSubmit={handleSubmit}
          className="max-h-[90vh] overflow-y-auto overflow-x-hidden flex flex-col"
        >
          <DialogHeader className="p-6 pb-4">
            <DialogTitle className="text-xl">{title}</DialogTitle>
          </DialogHeader>

          <div className="px-6 pb-6">
            <div className="grid gap-4">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter user type name"
                autoFocus
              />
            </div>
          </div>

          <DialogFooter className="px-6 py-4 border-t">
            <div className="flex justify-end gap-3 w-full">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
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
