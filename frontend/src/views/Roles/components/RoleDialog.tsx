import { useState, useEffect } from "react";
import { toast } from "react-hot-toast";
import { FormDialog } from "@/components/ui/form-dialog";
import { Input } from "@/components/input";
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

interface RoleDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onRoleSaved: () => void;
  roleToEdit?: Role | null;
  mode?: "create" | "edit";
}

export function RoleDialog({
  isOpen,
  onOpenChange,
  onRoleSaved,
  roleToEdit = null,
  mode = "create",
}: RoleDialogProps) {
  const [name, setName] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [roleId, setRoleId] = useState<string | undefined>("");
  const [dialogMode, setDialogMode] = useState<"create" | "edit">(mode);
  const [error, setError] = useState("");
  const [allPermissions, setAllPermissions] = useState<Permission[]>([]);
  const [rolePermissions, setRolePermissions] = useState<Permission[]>([]);
  const [selectedPermissionIds, setSelectedPermissionIds] = useState<string[]>(
    []
  );
  const [permissionsLoading, setPermissionsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    setDialogMode(mode);
  }, [mode]);

  useEffect(() => {
    if (isOpen) {
      resetForm();
      setError("");

      setAllPermissions([]);
      setRolePermissions([]);
      setSelectedPermissionIds([]);
      setSearchQuery("");

      if (roleToEdit && dialogMode === "edit") {
        populateFormWithRoleData(roleToEdit);
      }
      fetchPermissions();
    }
  }, [isOpen, roleToEdit, dialogMode]);

  const fetchPermissions = async () => {
    setPermissionsLoading(true);
    try {
      const permissions = await getAllPermissions();
      setAllPermissions(permissions);

      if (roleToEdit && roleToEdit.id) {
        const rolePermissionIds = await getPermissionsByRoleId(roleToEdit.id);

        const rolePermissionObjects = permissions.filter((permission) =>
          rolePermissionIds.includes(permission.id)
        );

        setRolePermissions(rolePermissionObjects);
        setSelectedPermissionIds(rolePermissionIds);
      }
    } catch (error) {
      toast.error("Error fetching permissions");
    } finally {
      setPermissionsLoading(false);
    }
  };

  const populateFormWithRoleData = (role: Role) => {
    setRoleId(role.id);
    setName(role.name || "");
    setIsActive(role.is_active === 1);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!name.trim()) {
      setError("Role name is required");
      return;
    }

    try {
      setIsSubmitting(true);
      const roleData: Partial<Role> = {
        name: name.trim(),
        is_active: isActive ? 1 : 0,
      };

      let savedRoleId = roleId;
      if (dialogMode === "create") {
        const createdRole = await createRole(roleData);
        savedRoleId = createdRole.id;
        toast.success("Role created successfully");
      } else {
        if (!roleId) {
          setError("Role ID is missing for update");
          return;
        }
        await updateRole(roleId, roleData);
        toast.success("Role updated successfully");
      }

      await saveRolePermissions(savedRoleId, selectedPermissionIds);
      onRoleSaved();
      onOpenChange(false);
      resetForm();
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : `Failed to ${dialogMode} role`;
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    if (dialogMode === "create") {
      setRoleId(undefined);
      setName("");
      setIsActive(true);
      setSelectedPermissionIds([]);
    }
  };
  const title = dialogMode === "create" ? "Create New Role" : "Edit Role";
  const submitButtonText =
    dialogMode === "create" ? "Create Role" : "Update Role";
  const loadingText = dialogMode === "create" ? "Creating..." : "Updating...";

  return (
    <FormDialog
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      title={title}
      description="Enter the details for the role"
      onSubmit={handleSubmit}
      isLoading={isSubmitting}
      submitButtonText={submitButtonText}
      loadingText={loadingText}
    >
      <div className="space-y-6">
        {error && (
          <div className="text-sm font-medium text-red-500">{error}</div>
        )}

        <div className="space-y-2">
          <Label htmlFor="name">Name</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter role name"
            autoFocus
          />
        </div>

        <div className="space-y-4">
          <>
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
            <Label>Permissions</Label>
            <div className="grid grid-cols-2 gap-4 max-h-60 overflow-y-auto">
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
                          className="break-all"
                          htmlFor={`permission-${permission.id}`}
                        >
                          {permission.name}
                        </label>
                      </div>
                    ))}
            </div>
          </>
        </div>

        <div className="flex items-center gap-2">
          <Label htmlFor="is-active">Active</Label>
          <Switch
            id="is-active"
            checked={isActive}
            onCheckedChange={setIsActive}
          />
        </div>
      </div>
    </FormDialog>
  );
}
