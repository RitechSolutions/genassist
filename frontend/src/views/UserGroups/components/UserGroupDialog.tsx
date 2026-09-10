import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { FormField } from "@/components/ui/form-field";
import { CRUDDialog } from "@/components/ui/crud-dialog";
import { extractErrorMessage } from "@/helpers/apiError";
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

type UserGroupFormValues = {
  name: string;
  description: string;
};

// Matches the String(500) description column on the user_group table.
const USER_GROUP_DESCRIPTION_MAX_LENGTH = 500;

export function UserGroupDialog({
  isOpen,
  onOpenChange,
  onGroupSaved,
  onGroupUpdated,
  groupToEdit = null,
  mode = "create",
}: UserGroupDialogProps) {
  return (
    <CRUDDialog<UserGroupFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={mode}
      maxWidth="480px"
      resetKey={groupToEdit?.id ?? null}
      initialValues={{ name: "", description: "" }}
      editValues={
        groupToEdit
          ? { name: groupToEdit.name, description: groupToEdit.description ?? "" }
          : null
      }
      title={{ create: "Create New User Group", edit: "Edit User Group" }}
      submitLabel={{ create: "Create Group", edit: "Update Group" }}
      loadingLabel={{ create: "Creating...", edit: "Updating..." }}
      successMessage={{
        create: "User group created successfully.",
        edit: "User group updated successfully.",
      }}
      errorMessage={(err, m) => {
        const detail = extractErrorMessage(err, "");
        return `Failed to ${m === "create" ? "create" : "update"} user group${
          detail ? `: ${detail}` : "."
        }`;
      }}
      validate={(values) =>
        !values.name.trim() ? { name: "Name is required." } : null
      }
      onSubmit={async (values, { mode: m }) => {
        const payload: Partial<UserGroup> = {
          name: values.name.trim(),
          description: values.description.trim() || null,
        };
        if (m === "create") {
          await createUserGroup(payload);
          onGroupSaved();
        } else {
          if (!groupToEdit?.id) return;
          const updated = await updateUserGroup(groupToEdit.id, payload);
          onGroupUpdated?.(updated);
        }
      }}
    >
      {({ values, setField, errors }) => (
        <>
          <FormField id="name" label="Name" error={errors.name}>
            <Input
              id="name"
              value={values.name}
              onChange={(e) => setField("name", e.target.value)}
              placeholder="Enter group name"
              autoFocus
            />
          </FormField>

          <FormField id="description" label="Description">
            <Textarea
              id="description"
              size="description"
              maxLength={USER_GROUP_DESCRIPTION_MAX_LENGTH}
              value={values.description}
              onChange={(e) => setField("description", e.target.value)}
              placeholder="Enter description (optional)"
            />
          </FormField>
        </>
      )}
    </CRUDDialog>
  );
}
