import { useState } from "react";
import { Dialog, DialogContent } from "@/components/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Switch } from "@/components/switch";
import { Label } from "@/components/label";
import { createUser, updateUser, getUser } from "@/services/users";
import { useEffect } from "react";
import { toast } from "react-hot-toast";
import { Info, Loader2 } from "lucide-react";
import { Role } from "@/interfaces/role.interface";
import { UserType } from "@/interfaces/userType.interface";
import { User } from "@/interfaces/user.interface";
import { UserGroup } from "@/interfaces/userGroup.interface";
import { getAllUserTypes } from "@/services/userTypes";
import { getAllRoles } from "@/services/roles";
import { getAllUserGroups, addGroupSupervisor, removeGroupSupervisor } from "@/services/userGroups";
import { Badge } from "@/components/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/RadixTooltip";
import { getApiUrl } from "@/config/api";
import { isAxiosError } from "axios";
import { FormField } from "@/components/ui/form-field";
import { CRUDDialog, FieldErrors } from "@/components/ui/crud-dialog";
import { areUserRolesRequired } from "@/views/Users/helpers/userFormRules";
import { isSupervisorUser } from "../helpers/supervision";

// Value for the "No group" option, since Radix SelectItem cannot use an empty string value.
const NO_GROUP_VALUE = "__none__";

interface UserDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onUserCreated: () => void;
  onUserUpdated?: (user: User) => void;
  userToEdit?: User | null;
  mode?: "create" | "edit";
}

type UserFormValues = {
  username: string;
  email: string;
  password: string;
  apiKey: string;
  isActive: boolean;
  userTypeId: string;
  selectedRoleIds: string[];
  entraOid: string;
};

export function UserDialog({
  isOpen,
  onOpenChange,
  onUserCreated,
  onUserUpdated,
  userToEdit = null,
  mode = "create",
}: UserDialogProps) {
  // Fetched reference data (not part of the form values).
  const [roles, setRoles] = useState<Role[]>([]);
  const [userTypes, setUserTypes] = useState<UserType[]>([]);
  const [userGroups, setUserGroups] = useState<UserGroup[]>([]);
  // Group + supervised-group selection are kept in component state because they
  // are interdependent (a group cannot supervise itself) and drive a body-level
  // effect that CRUDDialog's render-prop cannot host.
  const [groupId, setGroupId] = useState<string>("");
  const [supervisedGroupIds, setSupervisedGroupIds] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">(mode);
  const [microsoftSsoEnabled, setMicrosoftSsoEnabled] = useState(false);
  // The fully-fetched user drives CRUDDialog's edit values; resetSeq forces a
  // re-initialization once the async fetch resolves after the dialog is open.
  const [editUser, setEditUser] = useState<User | null>(null);
  const [resetSeq, setResetSeq] = useState(0);

  useEffect(() => {
    setDialogMode(mode);
  }, [mode]);

  useEffect(() => {
    if (!isOpen) return;

    const sso_microsoft_enabled = import.meta.env.VITE_SSO_MICROSOFT_ENABLED === "true";
    setMicrosoftSsoEnabled(sso_microsoft_enabled);

    if (!sso_microsoft_enabled) return;

    let cancelled = false;
    (async () => {
      try {
        const base = await getApiUrl();
        const r = await fetch(`${base}auth/sso/microsoft/status`);
        if (!r.ok || cancelled) return;
        const data = (await r.json()) as { microsoft_sso_enabled?: boolean };
        if (!cancelled && data.microsoft_sso_enabled) {
          setMicrosoftSsoEnabled(true);
        }
      } catch {
        // keep false
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  const applyUser = (user: User) => {
    setEditUser(user);
    setGroupId(user.group_id ?? "");
    // Assignments only survive while the role does, a demoted user starts empty
    // so re-promotion cannot silently restore a previous stint's groups.
    setSupervisedGroupIds(isSupervisorUser(user) ? (user.supervised_group_ids ?? []) : []);
    setResetSeq((seq) => seq + 1);
  };

  const loadFormData = async () => {
    setIsLoading(true);
    try {
      const [rolesData, userTypesData, groupsData] = await Promise.all([
        getAllRoles().catch((error) => {
          toast.error("Failed to fetch roles.");
          return [];
        }),
        getAllUserTypes().catch((error) => {
          toast.error("Failed to fetch user types.");
          return [];
        }),
        getAllUserGroups().catch(() => []),
      ]);

      setRoles(rolesData);
      setUserTypes(userTypesData);
      setUserGroups(groupsData);
    } catch (error) {
      toast.error("Failed to fetch data.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadFormData();

      if (dialogMode === "create") {
        // CRUDDialog resets its own form values on open; reset the state it
        // does not own here.
        setEditUser(null);
        setGroupId("");
        setSupervisedGroupIds([]);
      }

      if (userToEdit && dialogMode === "edit") {
        if (userToEdit.id) {
          (async () => {
            try {
              const full = await getUser(userToEdit.id!);
              applyUser(full || userToEdit);
            } catch {
              applyUser(userToEdit);
            }
          })();
        } else {
          applyUser(userToEdit);
        }
      }
    }
  }, [isOpen, userToEdit, dialogMode]);

  useEffect(() => {
    setSupervisedGroupIds((prev) => prev.filter((id) => id !== groupId));
  }, [groupId]);

  if (isLoading) {
    return (
      <Dialog open={isOpen} onOpenChange={onOpenChange}>
        <DialogContent>
          <div className="flex items-center justify-center p-6">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <CRUDDialog<UserFormValues>
      open={isOpen}
      onOpenChange={onOpenChange}
      mode={dialogMode}
      maxWidth="600px"
      bodyClassName="space-y-4"
      resetKey={resetSeq}
      preventCloseWhileSubmitting={false}
      initialValues={{
        username: "",
        email: "",
        password: "",
        apiKey: "",
        isActive: true,
        userTypeId: "",
        selectedRoleIds: [],
        entraOid: "",
      }}
      editValues={
        editUser
          ? {
              username: editUser.username || "",
              email: editUser.email || "",
              password: "",
              apiKey: "",
              isActive: editUser.is_active === 1,
              userTypeId: editUser.user_type_id || editUser.user_type?.id || "",
              selectedRoleIds:
                editUser.role_ids || editUser.roles?.map((role) => role.id) || [],
              entraOid: editUser.entra_oid ?? "",
            }
          : null
      }
      title={{ create: "Create New User", edit: "Edit User" }}
      submitLabel={{ create: "Create User", edit: "Update User" }}
      loadingLabel={{ create: "Creating...", edit: "Updating..." }}
      successMessage={{
        create: "User created successfully.",
        edit: "User updated successfully.",
      }}
      errorMessage={(err, m) => {
        if ((err as { __userIdMissing?: boolean })?.__userIdMissing) {
          return "User ID is required.";
        }
        if ((err as { __supervisedSyncFailed?: boolean })?.__supervisedSyncFailed) {
          return "User saved, but supervised groups could not be updated. Reopen to retry.";
        }
        const data = isAxiosError(err)
          ? (err.response?.data as Record<string, unknown> | undefined)
          : undefined;
        const status = isAxiosError(err) ? err.response?.status : undefined;
        let detail = "";

        if (status === 400) {
          if (data?.error_key === "EMAIL_ALREADY_EXISTS") {
            detail = "A user with this email already exists.";
          } else if (data?.error_key === "USER_ROLES_REQUIRED") {
            detail = "At least one role is required.";
          } else {
            detail = "A user with this username already exists.";
          }
        } else if (status === 409 && data?.error_key === "ENTRA_OID_IN_USE") {
          detail = "This Microsoft Entra object ID is already linked to another user.";
        } else if (data && typeof data.error === "string") {
          detail = data.error;
        } else if (
          data?.detail &&
          Array.isArray(data.detail) &&
          data.detail[0] &&
          typeof (data.detail[0] as { ctx?: { reason?: string } }).ctx?.reason === "string"
        ) {
          detail = (data.detail[0] as { ctx: { reason: string } }).ctx.reason;
        }

        return `Failed to ${m} user${detail ? `: ${detail}` : "."}`;
      }}
      validate={(values) => {
        const selectedUserType = userTypes.find(
          (type) => type.id === values.userTypeId
        );
        const isConsole = selectedUserType?.name?.toLowerCase() === "console";
        const passwordRequired =
          dialogMode === "create" && !values.apiKey && !isConsole;

        const validationErrors: FieldErrors<UserFormValues> = {};
        if (!values.username) validationErrors.username = "Username is required.";
        if (!values.email) validationErrors.email = "Email is required.";
        if (!values.userTypeId) validationErrors.userTypeId = "Type is required.";
        if (passwordRequired && !values.password) {
          validationErrors.password = "Password is required.";
        }
        if (
          areUserRolesRequired(dialogMode, selectedUserType?.name) &&
          values.selectedRoleIds.length === 0
        ) {
          validationErrors.selectedRoleIds = "Roles is required.";
        }

        return Object.keys(validationErrors).length ? validationErrors : null;
      }}
      onSubmit={async (values, { mode: m }) => {
        const userData: Partial<User> = {
          username: values.username,
          email: values.email,
          is_active: values.isActive ? 1 : 0,
          user_type_id: values.userTypeId,
          role_ids: values.selectedRoleIds,
          group_id: groupId || null,
        };

        if (m === "create" || values.password) {
          userData.password = values.password || values.apiKey || values.email;
        }

        if (microsoftSsoEnabled) {
          userData.entra_oid = values.entraOid.trim() ? values.entraOid.trim() : null;
        }

        if (m === "create") {
          await createUser(userData as User);
          onUserCreated();
        } else {
          const uid = editUser?.id;
          if (!uid) {
            throw Object.assign(new Error("User ID is required."), {
              __userIdMissing: true,
            });
          }
          await updateUser(uid, userData);

          const stillSupervisor = roles
            .filter((r) => values.selectedRoleIds.includes(r.id))
            .some((r) => r.name?.toLowerCase() === "supervisor");

          if (stillSupervisor) {
            // The PUT resolves before these run, and a promotion clears prior
            // assignments server-side, so the diff needs the post-update record.
            // Without it a deselection would diff against nothing and be dropped.
            const current = await getUser(uid).catch(() => null);
            if (!current) {
              throw Object.assign(new Error("Supervised groups not synced."), {
                __supervisedSyncFailed: true,
              });
            }
            const previousIds = current.supervised_group_ids ?? [];
            const toAdd = supervisedGroupIds.filter((id) => !previousIds.includes(id));
            const toRemove = previousIds.filter((id) => !supervisedGroupIds.includes(id));
            await Promise.all([
              ...toAdd.map((gid) => addGroupSupervisor(gid, uid)),
              ...toRemove.map((gid) => removeGroupSupervisor(gid, uid)),
            ]);
          }

          if (onUserUpdated) {
            // The save is already committed — a failed read-back only leaves the
            // row stale, so it must not surface as a failed edit.
            const finalUser = await getUser(uid).catch(() => null);
            if (finalUser) onUserUpdated(finalUser);
          }
        }
      }}
    >
      {(form) => {
        const { values, setField, errors, mode: m } = form;
        const selectedUserType = userTypes.find(
          (type) => type.id === values.userTypeId
        );
        const isConsoleUserType =
          selectedUserType?.name?.toLowerCase() === "console";
        const isSupervisor = roles.some(
          (r) =>
            values.selectedRoleIds.includes(r.id) &&
            r.name?.toLowerCase() === "supervisor"
        );

        const rolesRequired = areUserRolesRequired(m, selectedUserType?.name);

        const handleRoleToggle = (roleId: string) => {
          form.setValues((prev) => {
            if (
              rolesRequired &&
              prev.selectedRoleIds.includes(roleId) &&
              prev.selectedRoleIds.length === 1
            ) {
              toast.error("At least one role is required.");
              return prev;
            }
            return {
              ...prev,
              selectedRoleIds: prev.selectedRoleIds.includes(roleId)
                ? prev.selectedRoleIds.filter((id) => id !== roleId)
                : [...prev.selectedRoleIds, roleId],
            };
          });
          form.setFieldError("selectedRoleIds", undefined);
        };

        return (
          <>
            <div className="grid grid-cols-2 gap-4">
              <FormField id="username" label="Username" error={errors.username}>
                <Input
                  id="username"
                  value={values.username}
                  onChange={(e) => setField("username", e.target.value)}
                  placeholder="Enter username"
                  disabled={m === "edit"}
                />
              </FormField>
              <FormField id="email" label="Email" error={errors.email}>
                <Input
                  id="email"
                  type="email"
                  value={values.email}
                  onChange={(e) => setField("email", e.target.value)}
                  placeholder="Enter email"
                />
              </FormField>
            </div>

            {microsoftSsoEnabled && (
              <FormField id="entra-oid" label="Microsoft Entra ID">
                <div className="space-y-2">
                  <Input
                    id="entra-oid"
                    value={values.entraOid}
                    onChange={(e) => setField("entraOid", e.target.value)}
                    placeholder="Entra ID — optional, for SSO pre-linking"
                    autoComplete="off"
                  />
                  <p className="text-xs text-muted-foreground">
                    Must match the user&apos;s <code className="text-xs">oid</code> claim from the ID token.
                    {m === "edit"
                      ? " Clear the field to unlink this account from Entra SSO."
                      : " Leave blank to link automatically on first sign-in when the email matches."}
                  </p>
                </div>
              </FormField>
            )}

            <div
              className={`grid gap-4 ${
                isConsoleUserType ? "grid-cols-1" : "grid-cols-2"
              }`}
            >
              <FormField id="userType" label="Type" error={errors.userTypeId}>
                {userTypes.length === 0 ? (
                  <div className="text-sm text-muted-foreground italic">
                    No user types available
                  </div>
                ) : (
                  <Select
                    value={values.userTypeId}
                    onValueChange={(value) => {
                      setField("userTypeId", value);
                      form.setFieldError("selectedRoleIds", undefined);
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      {userTypes.map((type) => (
                        <SelectItem key={type.id} value={type.id}>
                          {type.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </FormField>
              {!isConsoleUserType && (
                <FormField
                  id="password"
                  label={m === "create" ? "Password" : "New Password"}
                  error={errors.password}
                >
                  <Input
                    id="password"
                    type="password"
                    value={values.password}
                    onChange={(e) => setField("password", e.target.value)}
                    placeholder={
                      m === "create"
                        ? "Enter password"
                        : "Enter new password (optional)"
                    }
                  />
                </FormField>
              )}
            </div>

            <div className="flex items-center gap-2">
              <Label htmlFor="is-active">Active</Label>
              <Switch
                id="is-active"
                checked={values.isActive}
                onCheckedChange={(checked) => setField("isActive", checked)}
              />
            </div>

            <FormField label="Roles" error={errors.selectedRoleIds}>
              <div className="grid grid-cols-2 gap-2 border rounded-lg p-4">
                {roles
                  .filter((role) => role.role_type !== "internal")
                  .map((role) => {
                    const isChecked = values.selectedRoleIds.includes(role.id);
                    return (
                      <div key={role.id} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          id={`role-${role.id}`}
                          value={role.id}
                          checked={isChecked}
                          onChange={() => handleRoleToggle(role.id)}
                          className="form-checkbox accent-primary w-4 h-4"
                        />
                        <Label
                          htmlFor={`role-${role.id}`}
                          className="cursor-pointer"
                        >
                          {role.name}
                        </Label>
                      </div>
                    );
                  })}
              </div>
            </FormField>

            {userGroups.length > 0 && (
              <div className="space-y-2">
                <Label htmlFor="group">Group</Label>
                <Select
                  value={groupId || NO_GROUP_VALUE}
                  onValueChange={(value) =>
                    setGroupId(value === NO_GROUP_VALUE ? "" : value)
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select group (optional)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_GROUP_VALUE}>No group</SelectItem>
                    {userGroups.map((g) => (
                      <SelectItem key={g.id} value={g.id}>
                        {g.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {userGroups.length > 0 && isSupervisor && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Label>Supervise Other Groups</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                        aria-label="Supervise Other Groups info"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-balance">
                      This user will be part of the selected group, and can
                      supervise other groups (optional).
                    </TooltipContent>
                  </Tooltip>
                </div>
                <div className="grid grid-cols-2 gap-2 border rounded-lg p-4">
                  {userGroups.map((g) => {
                    const isCurrentGroup = g.id === groupId;
                    const isLockedByMissingGroup = !groupId;
                    return (
                    <div key={g.id} className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id={`sg-${g.id}`}
                        checked={isCurrentGroup || supervisedGroupIds.includes(g.id)}
                        disabled={isLockedByMissingGroup}
                        aria-disabled={isLockedByMissingGroup || isCurrentGroup}
                        tabIndex={isCurrentGroup ? -1 : undefined}
                        onChange={() =>
                          isCurrentGroup
                            ? null
                            :
                          setSupervisedGroupIds((prev) =>
                            prev.includes(g.id)
                              ? prev.filter((id) => id !== g.id)
                              : [...prev, g.id]
                          )
                        }
                        className={`form-checkbox accent-primary w-4 h-4 disabled:opacity-40 ${
                          isCurrentGroup ? "opacity-60 cursor-not-allowed pointer-events-none" : ""
                        }`}
                      />
                      <div className="flex items-center gap-2">
                        <Label htmlFor={`sg-${g.id}`} className={!groupId ? "text-muted-foreground" : "cursor-pointer"}>
                          {g.name}
                        </Label>
                        {isCurrentGroup && (
                          <Badge variant="secondary" className="text-[10px] uppercase tracking-wide">
                            Current
                          </Badge>
                        )}
                      </div>
                    </div>
                  )})}
                </div>
                {!groupId && (
                  <p className="text-xs text-muted-foreground">
                    Select a group first to enable supervision options.
                  </p>
                )}
              </div>
            )}
          </>
        );
      }}
    </CRUDDialog>
  );
}
