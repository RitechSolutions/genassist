import { useEffect, useRef, useState } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { FormField } from "@/components/ui/form-field";
import { CRUDDialog } from "@/components/ui/crud-dialog";
import { extractErrorMessage } from "@/helpers/apiError";
import { Permission } from "@/interfaces/permission.interface";
import { Role } from "@/interfaces/role.interface";
import {
  getAllPermissions,
  getPermissionsByRoleId,
  saveRolePermissions,
} from "@/services/permission";
import { createRole, updateRole } from "@/services/roles";
import { PermissionPicker } from "@/views/Roles/components/PermissionPicker";

/** The one role the API lets hold admin-reserved permissions. */
const ADMIN_ROLE_NAME = "admin";

interface RoleDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onRoleSaved: () => void;
  onRoleUpdated?: (role: Role) => void;
  roleToEdit?: Role | null;
  mode?: "create" | "edit";
}

type RoleFormValues = {
  name: string;
  is_active: boolean;
};

export function RoleDialog({
  isOpen,
  onOpenChange,
  onRoleSaved,
  onRoleUpdated,
  roleToEdit = null,
  mode = "create",
}: RoleDialogProps) {
  const [allPermissions, setAllPermissions] = useState<Permission[]>([]);
  const [selectedPermissionIds, setSelectedPermissionIds] = useState<string[]>([]);
  const [permissionsLoading, setPermissionsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Guards against a slow response from a previously opened role landing in the
  // dialog after it has been reopened for a different one.
  const requestIdRef = useRef(0);
  // Set once a role has been created but its permissions failed to save, so a
  // retry updates that role instead of creating a second one.
  const createdRoleIdRef = useRef<string | null>(null);

  const loadPermissions = async () => {
    const requestId = ++requestIdRef.current;
    const isCurrent = () => requestId === requestIdRef.current;

    setPermissionsLoading(true);
    setLoadError(null);

    try {
      const permissions = await getAllPermissions();
      const rolePermissionIds = roleToEdit?.id
        ? await getPermissionsByRoleId(roleToEdit.id)
        : [];

      if (!isCurrent()) return;
      setAllPermissions(permissions);
      setSelectedPermissionIds(rolePermissionIds);
    } catch (error) {
      if (!isCurrent()) return;
      // Never fall back to an empty selection: saving that would wipe the
      // role's real permissions.
      setAllPermissions([]);
      setSelectedPermissionIds([]);
      setLoadError(
        extractErrorMessage(error, "Could not load permissions. Close and try again.")
      );
    } finally {
      // Must stay last: the picker mounts on this flip and decides which areas
      // start expanded from the selection above.
      if (isCurrent()) setPermissionsLoading(false);
    }
  };

  useEffect(() => {
    if (!isOpen) {
      // Invalidate any in-flight load so it cannot apply to the next open.
      requestIdRef.current++;
      return;
    }

    createdRoleIdRef.current = null;
    setAllPermissions([]);
    setSelectedPermissionIds([]);
    loadPermissions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, roleToEdit?.id, mode]);

  return (
    <CRUDDialog<RoleFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={mode}
      maxWidth="720px"
      resetKey={roleToEdit?.id ?? null}
      initialValues={{ name: "", is_active: true }}
      editValues={
        roleToEdit
          ? { name: roleToEdit.name || "", is_active: roleToEdit.is_active === 1 }
          : null
      }
      title={{ create: "Create New Role", edit: "Edit Role" }}
      submitLabel={{ create: "Create Role", edit: "Update Role" }}
      loadingLabel={{ create: "Creating...", edit: "Updating..." }}
      successMessage={{
        create: "Role created successfully.",
        edit: "Role updated successfully.",
      }}
      errorMessage={(err, m) => {
        const status = (err as { status?: number })?.status;
        const detail =
          status === 400
            ? "A role with this name already exists."
            : extractErrorMessage(err, "");
        return `Failed to ${m} role${detail ? `: ${detail}` : "."}`;
      }}
      validate={(values) =>
        !values.name.trim() ? { name: "Name is required." } : null
      }
      submitDisabled={permissionsLoading || loadError !== null}
      onSubmit={async (values, { mode: m }) => {
        const roleData: Partial<Role> = {
          name: values.name.trim(),
          is_active: values.is_active ? 1 : 0,
        };

        if (m === "create") {
          // A previous attempt may have created the role and then failed to
          // save its permissions; reuse it so the retry can't duplicate it.
          const pendingRoleId = createdRoleIdRef.current;
          let roleId: string;

          if (pendingRoleId) {
            await updateRole(pendingRoleId, roleData);
            roleId = pendingRoleId;
          } else {
            roleId = (await createRole(roleData)).id;
            createdRoleIdRef.current = roleId;
          }

          try {
            await saveRolePermissions(roleId, selectedPermissionIds);
          } catch (error) {
            // The role itself exists now, so let the list show it.
            onRoleSaved();
            throw error;
          }

          createdRoleIdRef.current = null;
          onRoleSaved();
        } else {
          if (!roleToEdit?.id) {
            throw new Error("Role ID is required.");
          }
          await updateRole(roleToEdit.id, roleData);
          await saveRolePermissions(roleToEdit.id, selectedPermissionIds);
          onRoleUpdated?.({ ...roleToEdit, ...roleData });
        }
      }}
    >
      {({ values, setField, errors }) => (
        <>
          <div className="flex items-start gap-4">
            <div className="flex-1">
              <FormField id="name" label="Name" error={errors.name}>
                <Input
                  id="name"
                  value={values.name}
                  onChange={(e) => setField("name", e.target.value)}
                  placeholder="Enter role name"
                  autoFocus
                />
              </FormField>
            </div>

            <div className="flex flex-col gap-2 pt-1">
              <Label htmlFor="is-active">Active</Label>
              <Switch
                id="is-active"
                checked={values.is_active}
                onCheckedChange={(checked) => setField("is_active", checked)}
              />
            </div>
          </div>

          {permissionsLoading ? (
            <div className="flex flex-col items-center justify-center gap-4 rounded-md border p-8">
              <Loader2 className="h-6 w-6 animate-spin" />
              <span className="text-sm font-medium text-muted-foreground">
                Loading permissions...
              </span>
            </div>
          ) : loadError ? (
            <div className="flex flex-col items-center gap-3 rounded-md border border-destructive/40 bg-destructive/5 p-6 text-center">
              <AlertCircle className="h-6 w-6 text-destructive" />
              <p className="text-sm text-muted-foreground">{loadError}</p>
              <Button type="button" variant="outline" size="sm" onClick={loadPermissions}>
                Retry
              </Button>
            </div>
          ) : (
            <PermissionPicker
              key={roleToEdit?.id ?? "create"}
              permissions={allPermissions}
              selectedIds={selectedPermissionIds}
              onChange={setSelectedPermissionIds}
              canAssignAdminOnly={values.name.trim() === ADMIN_ROLE_NAME}
            />
          )}
        </>
      )}
    </CRUDDialog>
  );
}
