import { UserType } from "@/interfaces/userType.interface";
import { Input } from "@/components/ui/input";
import { FormField } from "@/components/ui/form-field";
import { CRUDDialog } from "@/components/ui/crud-dialog";
import { updateUserType, createUserType } from "@/services/userTypes";

interface UserTypeDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onUserTypeSaved: () => void;
  onUserTypeUpdated?: (userType: UserType) => void;
  userTypeToEdit?: UserType | null;
  mode?: "create" | "edit";
}

type UserTypeFormValues = {
  name: string;
};

export function UserTypeDialog({
  isOpen,
  onOpenChange,
  onUserTypeSaved,
  onUserTypeUpdated,
  userTypeToEdit = null,
  mode = "create",
}: UserTypeDialogProps) {
  return (
    <CRUDDialog<UserTypeFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={mode}
      resetKey={userTypeToEdit?.id ?? null}
      initialValues={{ name: "" }}
      editValues={userTypeToEdit ? { name: userTypeToEdit.name ?? "" } : null}
      title={{ create: "Create New User Type", edit: "Edit User Type" }}
      submitLabel={{ create: "Create User Type", edit: "Update User Type" }}
      loadingLabel={{ create: "Creating...", edit: "Updating..." }}
      successMessage={{
        create: "User type created successfully.",
        edit: "User type updated successfully.",
      }}
      errorMessage={(err, m) => {
        const status = (err as { status?: number })?.status;
        if (status === 400) {
          return `Failed to ${m} user type: A user type with this name already exists.`;
        }
        return `Failed to ${m} user type.`;
      }}
      validate={(values) =>
        !values.name.trim() ? { name: "Name is required." } : null
      }
      onSubmit={async (values, { mode: m }) => {
        const payload: Partial<UserType> = { name: values.name.trim() };
        if (m === "create") {
          await createUserType(payload);
        } else {
          if (!userTypeToEdit?.id) {
            throw new Error("User type ID is required.");
          }
          await updateUserType(userTypeToEdit.id, payload);
        }
      }}
      onSuccess={(values, { mode: m }) => {
        if (m === "create") {
          onUserTypeSaved();
        } else if (onUserTypeUpdated && userTypeToEdit) {
          onUserTypeUpdated({ ...userTypeToEdit, name: values.name.trim() });
        }
      }}
    >
      {({ values, setField, errors }) => (
        <FormField id="name" label="Name" error={errors.name}>
          <Input
            id="name"
            value={values.name}
            onChange={(e) => setField("name", e.target.value)}
            placeholder="Enter user type name"
            autoFocus
          />
        </FormField>
      )}
    </CRUDDialog>
  );
}
