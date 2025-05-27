import { useEffect, useState } from "react";
import { UserType } from "@/interfaces/userType.interface";
import { toast } from "react-hot-toast";
import { FormDialog } from "@/components/ui/form-dialog";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { updateUserType, createUserType } from "@/services/userTypes";

interface UserTypeDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onUserTypeSaved: () => void;
  userTypeToEdit?: UserType | null;
  mode?: 'create' | 'edit';
}

export function UserTypeDialog({
  isOpen,
  onOpenChange,
  onUserTypeSaved,
  userTypeToEdit = null,
  mode = 'create'
}: UserTypeDialogProps) {
  const [name, setName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [userTypeId, setUserTypeId] = useState<string | undefined>(undefined);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>(mode);
  const [error, setError] = useState("");

  const title = dialogMode === 'create' ? 'Create New User Type' : 'Edit User Type';
  const submitButtonText = dialogMode === 'create' ? 'Create User Type' : 'Update User Type';
  const loadingText = dialogMode === 'create' ? 'Creating...' : 'Updating...';

  useEffect(() => {
    setDialogMode(mode);
  }, [mode]);

  useEffect(() => {
    if (isOpen) {
      resetForm();
      setError("");
      
      if (userTypeToEdit && dialogMode === 'edit') {
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
    setError("");
    
    if (!name.trim()) {
      setError("User type name is required");
      return;
    }

    try {
      setIsSubmitting(true);
      const userTypeData: Partial<UserType> = {
        name: name.trim(),
      };

      if (dialogMode === 'create') {
        await createUserType(userTypeData);
        toast.success("User type created successfully");
      } else {
        if (!userTypeId) {
          setError("User type ID is missing for update");
          return;
        }
        await updateUserType(userTypeId, userTypeData);
        toast.success("User type updated successfully");
      }

      onUserTypeSaved();
      onOpenChange(false);
      resetForm();
    } catch (err) {
      const errorMessage = err instanceof Error 
        ? err.message 
        : `Failed to ${dialogMode} user type`;
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    if (dialogMode === 'create') {
      setUserTypeId(undefined);
      setName("");
    }
  };

  return (
    <FormDialog
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      title={title}
      description="Enter the details for the user type"
      onSubmit={handleSubmit}
      isLoading={isSubmitting}
      submitButtonText={submitButtonText}
      loadingText={loadingText}
    >
      <div className="grid gap-4 py-4">
        {error && (
          <div className="text-sm font-medium text-red-500">
            {error}
          </div>
        )}
        
        <Label htmlFor="name">Name</Label>
        <Input
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter user type name"
          autoFocus
        />
      </div>
    </FormDialog>
  );
}