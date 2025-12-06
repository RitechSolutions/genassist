import { useState, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
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
import { Loader2 } from "lucide-react";
import { Role } from "@/interfaces/role.interface";
import { UserType } from "@/interfaces/userType.interface";
import { User } from "@/interfaces/user.interface";
import { getAllUserTypes } from "@/services/userTypes";
import { getAllRoles } from "@/services/roles";

interface UserDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onUserCreated: () => void;
  onUserUpdated?: (user: User) => void;
  userToEdit?: User | null;
  mode?: "create" | "edit";
}

export function UserDialog({
  isOpen,
  onOpenChange,
  onUserCreated,
  onUserUpdated,
  userToEdit = null,
  mode = "create",
}: UserDialogProps) {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [userTypeId, setUserTypeId] = useState<string>("");
  const [roles, setRoles] = useState<Role[]>([]);
  const [userTypes, setUserTypes] = useState<UserType[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [userId, setUserId] = useState<string | undefined>("");
  const [dialogMode, setDialogMode] = useState<"create" | "edit">(mode);

  useEffect(() => {
    setDialogMode(mode);
  }, [mode]);

  useEffect(() => {
    if (isOpen) {
      loadFormData();
      resetForm();

      if (userToEdit && dialogMode === "edit") {
        populateFormWithUserData(userToEdit);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, userToEdit, dialogMode]);

  const populateFormWithUserData = (user: User) => {
    setUserId(user.id);
    setUsername(user.username || "");
    setEmail(user.email || "");
    setPassword("");
    setApiKey("");
    setIsActive(user.is_active === 1);
    setUserTypeId(user.user_type_id || user.user_type?.id || "");
    setSelectedRoleIds(
      user.role_ids || user.roles?.map((role) => role.id) || []
    );
  };

  const loadFormData = async () => {
    setIsLoading(true);
    try {
      const [rolesData, userTypesData] = await Promise.all([
        getAllRoles().catch((error) => {
          toast.error("Failed to fetch roles.");
          return [];
        }),
        getAllUserTypes().catch((error) => {
          toast.error("Failed to fetch user types.");
          return [];
        }),
      ]);

      setRoles(rolesData);
      setUserTypes(userTypesData);
    } catch (error) {
      toast.error("Failed to fetch data.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    let requiredFields = [
      { label: "Username", isEmpty: !username },
      { label: "Email", isEmpty: !email },
      { label: "Type", isEmpty: !userTypeId },
      { label: "Password", isEmpty: !password },
      { label: "Roles", isEmpty: selectedRoleIds.length === 0 },
    ];

    if (dialogMode !== "create" || apiKey || isConsoleUserType) {
      requiredFields = requiredFields.filter(
        (field) => field.label !== "Password"
      );
    }

    const missingFields = requiredFields
      .filter((field) => field.isEmpty)
      .map((field) => field.label);

    if (missingFields.length > 0) {
      if (missingFields.length === 1) {
        toast.error(`${missingFields[0]} is required.`);
      } else {
        toast.error(`Please provide: ${missingFields.join(", ")}.`);
      }
      return;
    }

    setIsSubmitting(true);
    try {
      const userData: Partial<User> = {
        username,
        email,
        is_active: isActive ? 1 : 0,
        user_type_id: userTypeId,
        role_ids: selectedRoleIds,
      };

      if (dialogMode === "create" || password) {
        userData.password = password || apiKey || email;
      }

      if (dialogMode === "create") {
        await createUser(userData as User);
        toast.success("User created successfully.");
        onUserCreated();
      } else {
        if (!userId) {
          toast.error("User ID is required.");
          return;
        }
        await updateUser(userId, userData);
        toast.success("User updated successfully.");

        // Call onUserUpdated for edit mode with userData
        if (onUserUpdated && userToEdit) {
          const updatedUser: User = {
            ...userToEdit,
            ...userData,
            user_type:
              userTypes.find((type) => type.id === userTypeId) ||
              userToEdit.user_type,
            roles: roles.filter((role) => selectedRoleIds.includes(role.id)),
          };
          onUserUpdated(updatedUser);
        }
      }

      onOpenChange(false);
      resetForm();
    } catch (error) {
      const data = error.response.data;
      let errorMessage = "";

      if (error.status === 400) {
        errorMessage = "A user with this username already exists.";
      } else if (data.error) {
        errorMessage = data.error;
      } else if (data.detail) {
        errorMessage = data.detail["0"].ctx.reason;
      }

      toast.error(
        `Failed to ${dialogMode} user${
          errorMessage ? `: ${errorMessage}` : "."
        }`
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    if (dialogMode === "create") {
      setUserId(undefined);
      setUsername("");
      setEmail("");
      setPassword("");
      setApiKey("");
      setIsActive(true);
      setSelectedRoleIds([]);
      setUserTypeId("");
    }
  };

  const handleRoleToggle = (roleId: string) => {
    setSelectedRoleIds((prev) =>
      prev.includes(roleId)
        ? prev.filter((id) => id !== roleId)
        : [...prev, roleId]
    );
  };

  const isConsoleUserType = useMemo(() => {
    const selectedUserType = userTypes.find((type) => type.id === userTypeId);
    return selectedUserType?.name?.toLowerCase() === "console";
  }, [userTypes, userTypeId]);

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
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] p-0 overflow-hidden">
        <form
          onSubmit={handleSubmit}
          className="max-h-[90vh] overflow-y-auto overflow-x-hidden flex flex-col"
        >
          <DialogHeader className="p-6 pb-4">
            <div className="flex justify-between items-center">
              <DialogTitle>
                {dialogMode === "create" ? "Create New User" : "Edit User"}
              </DialogTitle>
            </div>
          </DialogHeader>
          <div className="px-6 pb-6 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter username"
                  disabled={dialogMode === "edit"}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter email"
                />
              </div>
            </div>
            <div
              className={`grid gap-4 ${
                isConsoleUserType ? "grid-cols-1" : "grid-cols-2"
              }`}
            >
              <div className="space-y-2">
                <Label htmlFor="userType">Type</Label>
                {userTypes.length === 0 ? (
                  <div className="text-sm text-muted-foreground italic">
                    No user types available
                  </div>
                ) : (
                  <Select
                    value={userTypeId}
                    onValueChange={(value) => setUserTypeId(value)}
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
              </div>
              {!isConsoleUserType && (
                <div className="space-y-2">
                  <Label htmlFor="password">
                    {dialogMode === "create" ? "Password" : "New Password"}
                  </Label>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={
                      dialogMode === "create"
                        ? "Enter password"
                        : "Enter new password (optional)"
                    }
                  />
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Label htmlFor="is-active">Active</Label>
              <Switch
                id="is-active"
                checked={isActive}
                onCheckedChange={setIsActive}
              />
            </div>
            <div className="space-y-2">
              <Label>Roles</Label>
              <div className="grid grid-cols-2 gap-2 border rounded-lg p-4">
                {roles
                  .filter((role) => role.role_type !== "internal")
                  .map((role) => {
                    const isChecked = selectedRoleIds.includes(role.id);
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
                    {dialogMode === "create" ? "Creating..." : "Updating..."}
                  </>
                ) : dialogMode === "create" ? (
                  "Create User"
                ) : (
                  "Update User"
                )}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
