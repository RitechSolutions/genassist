import { useCallback, useEffect, useState } from "react";
import { AxiosError } from "axios";
import { DataTable, Column } from "@/components/ui/data-table";
import { LIST_PAGE_SIZE } from "@/constants/pagination";
import { ActionButtons } from "@/components/ActionButtons";
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
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
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

  const filteredUsers = users.filter((user) => {
    const q = searchQuery.toLowerCase();
    if (!q) return true;
    const groupName = user.group_id ? (groupMap[user.group_id] ?? "") : "";
    return (
      user.username.toLowerCase().includes(q) ||
      user.email.toLowerCase().includes(q) ||
      (user.roles ?? []).some((r) => r.name?.toLowerCase().includes(q)) ||
      groupName.toLowerCase().includes(q)
    );
  });

  const currentUserId = getCurrentUserId();

  const handleDeleteClick = (user: User) => {
    setUserToDelete(user);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!userToDelete?.id) return;

    try {
      setIsDeleting(true);
      await deleteUser(userToDelete.id);
      toast.success("User deleted successfully.");
      setUsers((prev) => prev.filter((u) => u.id !== userToDelete.id));
    } catch (error) {
      const axiosError = error as AxiosError<{ error?: string }>;
      const apiMessage = axiosError.response?.data?.error;
      toast.error(apiMessage ?? "Failed to delete user.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setUserToDelete(null);
    }
  };

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
        const additionalGroupCount = new Set(
          (user.supervised_group_ids ?? []).filter(
            (id) => id && id !== user.group_id
          )
        ).size;
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
    {
      header: "Action",
      key: "action",
      cell: (user) => {
        const isDeleted = user.is_deleted === 1;
        const isSelf = Boolean(currentUserId && user.id === currentUserId);
        return (
          <ActionButtons
            canEdit={!isDeleted}
            canDelete={!isDeleted && !isSelf}
            canRevert={Boolean(isDeleted && isAdmin)}
            onEdit={() => onEditUser(user)}
            onDelete={() => handleDeleteClick(user)}
            onRevert={() => handleRevertClick(user)}
            editTitle="Edit User"
            deleteTitle="Delete User"
            revertTitle="Revert user"
          />
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

      <DataTable
        data={filteredUsers}
        columns={columns}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        pageSize={LIST_PAGE_SIZE}
        emptyMessage="No users found"
        notFoundMessage="No users found matching your search"
      />

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isInProgress={isDeleting}
        itemName={userToDelete?.username || ""}
        description={
          isAdmin
            ? `This will soft-delete the user "${userToDelete?.username}". They will be removed from the active list; admins can view them with "Show deleted users".`
            : `This will soft-delete the user "${userToDelete?.username}". They will be removed from the active list.`
        }
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
