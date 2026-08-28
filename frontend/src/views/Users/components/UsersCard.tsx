import { useCallback, useEffect, useState } from "react";
import { AxiosError } from "axios";
import { Column } from "@/components/ui/data-table";
import { EntityTableCard } from "@/components/EntityTableCard";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge } from "@/components/badge";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { deleteUser, getAllUsers, restoreUser } from "@/services/users";
import { getAllUserGroups } from "@/services/userGroups";
import { currentUserIsAdmin, getCurrentUserId } from "@/services/auth";
import { toast } from "react-hot-toast";
import { User } from "@/interfaces/user.interface";
import { UserGroup } from "@/interfaces/userGroup.interface";
import { activeSupervisedGroupIds } from "../helpers/supervision";

interface UsersCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditUser: (user: User) => void;
  updatedUser?: User | null;
}

export function UsersCard({
  searchQuery,
  refreshKey = 0,
  onEditUser,
  updatedUser = null,
}: UsersCardProps) {
  const isAdmin = currentUserIsAdmin();
  const [users, setUsers] = useState<User[]>([]);
  const [groupMap, setGroupMap] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showDeleted, setShowDeleted] = useState(false);
  const [userToRevert, setUserToRevert] = useState<User | null>(null);
  const [isRevertDialogOpen, setIsRevertDialogOpen] = useState(false);
  const [isReverting, setIsReverting] = useState(false);

  useEffect(() => {
    if (!isAdmin && showDeleted) {
      setShowDeleted(false);
    }
  }, [isAdmin, showDeleted]);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const [userData, groupsData] = await Promise.all([
        getAllUsers({ deletedOnly: showDeleted }),
        getAllUserGroups().catch(() => [] as UserGroup[]),
      ]);
      setUsers(userData);
      setGroupMap(Object.fromEntries(groupsData.map((g) => [g.id, g.name])));
      setError(null);
    } catch (err) {
      const axiosError = err as AxiosError<{ error?: string }>;
      if (axiosError.response?.status === 403 && showDeleted) {
        setShowDeleted(false);
      }
      const message =
        err instanceof Error ? err.message : "Failed to fetch users";
      setError(message);
      toast.error(
        axiosError.response?.data?.error ?? message
      );
    } finally {
      setLoading(false);
    }
  }, [showDeleted]);

  useEffect(() => {
    fetchUsers();
  }, [refreshKey, fetchUsers]);

  useEffect(() => {
    if (updatedUser) {
      setUsers((prevUsers) =>
        prevUsers.map((user) =>
          user.id === updatedUser.id ? updatedUser : user
        )
      );
    }
  }, [updatedUser]);

  const currentUserId = getCurrentUserId();

  const handleRevertClick = (user: User) => {
    setUserToRevert(user);
    setIsRevertDialogOpen(true);
  };

  const handleRevertConfirm = async () => {
    if (!userToRevert?.id) return;

    try {
      setIsReverting(true);
      await restoreUser(userToRevert.id);
      toast.success("User restored successfully.");
      setUsers((prev) => prev.filter((u) => u.id !== userToRevert.id));
    } catch (error) {
      const axiosError = error as AxiosError<{ error?: string }>;
      const apiMessage = axiosError.response?.data?.error;
      toast.error(apiMessage ?? "Failed to restore user.");
    } finally {
      setIsReverting(false);
      setIsRevertDialogOpen(false);
      setUserToRevert(null);
    }
  };

  const columns: Column<User>[] = [
    { header: "ID", key: "id", cell: (_user, index) => index + 1 },
    {
      header: "Username",
      key: "username",
      cell: (user) => user.username,
      className: "font-medium break-all",
    },
    {
      header: "Email",
      key: "email",
      cell: (user) => user.email,
      className: "truncate",
    },
    {
      header: "Status",
      key: "status",
      className: "overflow-hidden whitespace-nowrap text-clip",
      cell: (user) => (
        <div className="flex flex-wrap gap-1">
          <Badge variant={user.is_active === 1 ? "default" : "secondary"}>
            {user.is_active === 1 ? "Active" : "Inactive"}
          </Badge>
          {user.is_deleted === 1 && (
            <Badge variant="outline" className="text-muted-foreground">
              Deleted
            </Badge>
          )}
        </div>
      ),
    },
    {
      header: "User Type",
      key: "user_type",
      cell: (user) => user.user_type?.name || "N/A",
      className: "truncate",
    },
    {
      header: "Roles",
      key: "roles",
      className: "overflow-hidden whitespace-nowrap text-clip",
      cell: (user) => (
        <div className="flex gap-1 flex-wrap">
          {user.roles && user.roles.length > 0 ? (
            user.roles.map((role, roleIndex) => (
              <Badge key={roleIndex} variant="outline">
                {role.name}
              </Badge>
            ))
          ) : (
            <span className="text-muted-foreground">—</span>
          )}
        </div>
      ),
    },
    {
      header: "Group",
      key: "group",
      className: "truncate",
      cell: (user) => {
        const additionalGroupCount = new Set(activeSupervisedGroupIds(user)).size;
        return user.group_id ? (
          <div className="inline-flex items-center gap-1">
            <span>{groupMap[user.group_id] ?? "—"}</span>
            {additionalGroupCount > 0 && (
              <Badge variant="outline" className="px-1.5 py-0 text-[10px] leading-4">
                +{additionalGroupCount}
              </Badge>
            )}
          </div>
        ) : (
          "—"
        );
      },
    },
  ];

  return (
    <>
      {isAdmin && (
        <div className="mb-4 flex items-center gap-3">
          <Switch
            id="users-show-deleted"
            checked={showDeleted}
            onCheckedChange={(checked) => setShowDeleted(checked)}
          />
          <Label htmlFor="users-show-deleted" className="cursor-pointer font-normal">
            Show deleted users
          </Label>
        </div>
      )}

      <EntityTableCard<User>
        entityName="user"
        data={users}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        filterFn={(user, query) => {
          const q = query.toLowerCase();
          const groupName = user.group_id
            ? (groupMap[user.group_id] ?? "")
            : "";
          return (
            user.username.toLowerCase().includes(q) ||
            user.email.toLowerCase().includes(q) ||
            (user.roles ?? []).some((r) => r.name?.toLowerCase().includes(q)) ||
            groupName.toLowerCase().includes(q)
          );
        }}
        deleteFn={(user) => deleteUser(user.id!)}
        getItemName={(user) => user.username}
        deleteDescription={(user) =>
          isAdmin
            ? `This will soft-delete the user "${user.username}". They will be removed from the active list; admins can view them with "Show deleted users".`
            : `This will soft-delete the user "${user.username}". They will be removed from the active list.`
        }
        onDeleted={(user) =>
          setUsers((prev) => prev.filter((u) => u.id !== user.id))
        }
        emptyMessage="No users found"
        notFoundMessage="No users found matching your search"
        columns={columns}
        rowActions={{
          header: "Action",
          key: "action",
          onEdit: onEditUser,
          onRevert: handleRevertClick,
          editTitle: "Edit User",
          deleteTitle: "Delete User",
          revertTitle: "Revert user",
          canEdit: (user) => user.is_deleted !== 1,
          canDelete: (user) =>
            user.is_deleted !== 1 &&
            !(currentUserId && user.id === currentUserId),
          canRevert: (user) => Boolean(user.is_deleted === 1 && isAdmin),
        }}
      />

      <ConfirmDialog
        isOpen={isRevertDialogOpen}
        onOpenChange={setIsRevertDialogOpen}
        onConfirm={handleRevertConfirm}
        isInProgress={isReverting}
        title="Restore this user?"
        primaryButtonText="Revert"
        itemName={userToRevert?.username || ""}
        description={`This will remove the deleted state for "${userToRevert?.username}" and return them to the active user list.`}
      />
    </>
  );
}
