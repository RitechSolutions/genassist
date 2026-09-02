import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { Role } from "@/interfaces/role.interface";
import { createRole, updateRole } from "@/services/roles";
import { Permission } from "@/interfaces/permission.interface";
import {
  getAllPermissions,
  saveRolePermissions,
  getPermissionsByRoleId,
} from "@/services/permission";
import { Checkbox } from "@/components/checkbox";
import { Skeleton } from "@/components/skeleton";
import { FormField } from "@/components/ui/form-field";
import { CRUDDialog } from "@/components/ui/crud-dialog";
import { extractErrorMessage } from "@/helpers/apiError";
import { Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";

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
  const [selectedPermissionIds, setSelectedPermissionIds] = useState<string[]>(
    []
  );
  const [permissionsLoading, setPermissionsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [areAllPermissionsSelected, setAreAllPermissionsSelected] =
    useState(false);

  const handleToggleAllPermissions = () => {
    if (areAllPermissionsSelected) {
      setSelectedPermissionIds([]);
    } else {
      setSelectedPermissionIds(allPermissions.map((permission) => permission.id));
    }

    setAreAllPermissionsSelected(!areAllPermissionsSelected);
  };

  useEffect(() => {
    if (isOpen) {
      setAllPermissions([]);
      setSelectedPermissionIds([]);
      setSearchQuery("");
      fetchPermissions();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, roleToEdit, mode]);

  const fetchPermissions = async () => {
    setPermissionsLoading(true);
    try {
      const permissions = await getAllPermissions(mode);
      setAllPermissions(permissions);

      if (roleToEdit && roleToEdit.id) {
        const rolePermissionIds = await getPermissionsByRoleId(roleToEdit.id);
        setSelectedPermissionIds(rolePermissionIds);
      }
    } catch (error) {
      toast.error("Failed to fetch permissions.");
    } finally {
      setPermissionsLoading(false);
    }
  };

  return (
    <CRUDDialog<RoleFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={mode}
      maxWidth="700px"
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
      onSubmit={async (values, { mode: m }) => {
        const roleData: Partial<Role> = {
          name: values.name.trim(),
          is_active: values.is_active ? 1 : 0,
        };

        if (m === "create") {
          const createdRole = await createRole(roleData);
          await saveRolePermissions(createdRole.id, selectedPermissionIds);
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
          <FormField id="name" label="Name" error={errors.name}>
            <Input
              id="name"
              value={values.name}
              onChange={(e) => setField("name", e.target.value)}
              placeholder="Enter role name"
              autoFocus
            />
          </FormField>

          {/* Permissions */}
          {permissionsLoading ? (
            <div className="flex flex-col gap-4 items-center justify-center p-4">
              <Loader2 className="w-6 h-6 animate-spin" />
              <span className="text-sm text-muted-foreground font-medium">
                Loading permissions...
              </span>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="mb-3">
                <Label className="mt-2 mb-0.5" htmlFor="permission-search">
                  Search Permissions
                </Label>
                <Input
                  className="mt-2"
                  id="permission-search"
                  placeholder="Search..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <div className="flex items-center justify-between">
                <Label>Permissions</Label>
                <div className="flex items-center gap-2">
                  <Checkbox
                    checked={areAllPermissionsSelected}
                    onCheckedChange={handleToggleAllPermissions}
                    className="h-4 w-4"
                  />
                  <span className="text-sm font-medium">Select All</span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 max-h-64 overflow-y-auto pr-1">
                {allPermissions.length === 0
                  ? Array.from({ length: 6 }).map((_, index) => (
                      <div key={index} className="flex items-center gap-2">
                        <Skeleton className="h-4 w-4 rounded-sm" />
                        <Skeleton className="h-4 w-[150px]" />
                      </div>
                    ))
                  : [...allPermissions]
                      .filter((perm) =>
                        perm.name
                          .toLowerCase()
                          .includes(searchQuery.toLowerCase())
                      )
                      .map((permission) => (
                        <div
                          key={permission.id}
                          className="flex items-center gap-2"
                        >
                          <Checkbox
                            id={`permission-${permission.id}`}
                            checked={selectedPermissionIds.includes(
                              permission.id
                            )}
                            onCheckedChange={(checked) => {
                              const isChecked = checked === true;
                              if (isChecked) {
                                setSelectedPermissionIds((prev) => [
                                  ...prev,
                                  permission.id,
                                ]);
                              } else {
                                setSelectedPermissionIds((prev) =>
                                  prev.filter((id) => id !== permission.id)
                                );
                              }
                            }}
                          />
                          <label
                            className="break-all cursor-pointer"
                            htmlFor={`permission-${permission.id}`}
                          >
                            {permission.name}
                          </label>
                        </div>
                      ))}
              </div>
            </div>
          )}

          <div className="flex items-center gap-2">
            <Label htmlFor="is-active">Active</Label>
            <Switch
              id="is-active"
              checked={values.is_active}
              onCheckedChange={(checked) => setField("is_active", checked)}
            />
          </div>
        </>
      )}
    </CRUDDialog>
  );
}
