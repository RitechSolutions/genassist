import { useState, useEffect, useCallback } from "react";
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
import { Button } from "@/components/button";
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

export function RoleDialog({
  isOpen,
  onOpenChange,
  onRoleSaved,
  onRoleUpdated,
  roleToEdit = null,
  mode = "create",
}: RoleDialogProps) {
  const [name, setName] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [roleId, setRoleId] = useState<string | undefined>("");
  const [dialogMode, setDialogMode] = useState<"create" | "edit">(mode);
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


  const fetchPermissions = useCallback(async () => {
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
      toast.error("Failed to fetch permissions.");
    } finally {
      setPermissionsLoading(false);
    }
  }, [roleToEdit]);


  const populateFormWithRoleData = useCallback((role: Role) => {
    setRoleId(role.id);
    setName(role.name || "");
    setIsActive(role.is_active === 1);
  }, []);

  const resetForm = useCallback(() => {
    if (dialogMode === "create") {
      setRoleId(undefined);
      setName("");
      setIsActive(true);
      setSelectedPermissionIds([]);
    }
  }, [dialogMode]);

  useEffect(() => {
    if (isOpen) {
      resetForm();

      setAllPermissions([]);
      setRolePermissions([]);
      setSelectedPermissionIds([]);
      setSearchQuery("");

      if (roleToEdit && dialogMode === "edit") {
        populateFormWithRoleData(roleToEdit);
      }
      fetchPermissions();
    }
  }, [isOpen, roleToEdit, dialogMode, resetForm, populateFormWithRoleData, fetchPermissions]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      toast.error("Name is required.");
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
        toast.success("Role created successfully.");
        await saveRolePermissions(savedRoleId, selectedPermissionIds);
        onRoleSaved();
      } else {
        if (!roleId) {
          toast.error("Role ID is required.");
          return;
        }
        await updateRole(roleId, roleData);
        await saveRolePermissions(savedRoleId, selectedPermissionIds);
        toast.success("Role updated successfully.");
        if (onRoleUpdated && roleToEdit) {
          const updatedRole: Role = {
            ...roleToEdit,
            ...roleData,
          };
          onRoleUpdated(updatedRole);
        }
      }

      onOpenChange(false);
      resetForm();
    } catch (err) {
      const data = err.response.data;
      let errorMessage = "";

      if (err.status === 400) {
        errorMessage = "A role with this name already exists.";
      } else if (data.error) {
        errorMessage = data.error;
      } else if (data.detail) {
        errorMessage = data.detail["0"].msg;
      }

      toast.error(
        `Failed to ${dialogMode} role${
          errorMessage ? `: ${errorMessage}` : "."
        }`
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const title = dialogMode === "create" ? "Create New Role" : "Edit Role";
  const submitButtonText =
    dialogMode === "create" ? "Create Role" : "Update Role";
  const loadingText = dialogMode === "create" ? "Creating..." : "Updating...";

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[700px] p-0 overflow-hidden">
        <form onSubmit={handleSubmit}>
          <DialogHeader className="p-6 pb-4">
            <DialogTitle className="text-xl">{title}</DialogTitle>
          </DialogHeader>

          <div className="px-6 pb-6 space-y-6 max-h-[calc(90vh-160px)] overflow-y-auto overflow-x-hidden">
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

            <div className="flex items-center gap-2">
              <Label htmlFor="is-active">Active</Label>
              <Switch
                id="is-active"
                checked={isActive}
                onCheckedChange={setIsActive}
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
