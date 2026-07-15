import { useEffect, useMemo, useState } from "react";
import { AxiosError } from "axios";
import { DataTable, Column } from "@/components/ui/data-table";
import { LIST_PAGE_SIZE } from "@/constants/pagination";
import { ListEmptyState } from "@/components/ListEmptyState";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/button";
import { getAllUserGroups, deleteUserGroup } from "@/services/userGroups";
import { formatDate } from "@/helpers/utils";
import { UserGroup } from "@/interfaces/userGroup.interface";
import { toast } from "react-hot-toast";
import { UsersRound, Plus } from "lucide-react";

interface UserGroupsCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditGroup: (group: UserGroup) => void;
  updatedGroup?: UserGroup | null;
  onCreateGroup: () => void;
}

export function UserGroupsCard({
  searchQuery,
  refreshKey = 0,
  onEditGroup,
  updatedGroup = null,
  onCreateGroup,
}: UserGroupsCardProps) {
  const [groups, setGroups] = useState<UserGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [groupToDelete, setGroupToDelete] = useState<UserGroup | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    fetchGroups();
  }, [refreshKey]);

  useEffect(() => {
    if (updatedGroup) {
      setGroups((prev) =>
        prev.map((g) => (g.id === updatedGroup.id ? updatedGroup : g))
      );
    }
  }, [updatedGroup]);

  const fetchGroups = async () => {
    try {
      setLoading(true);
      const data = await getAllUserGroups();
      setGroups(data);
      setError(null);
    } catch {
      setError("Failed to fetch user groups");
      toast.error("Failed to fetch user groups.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteClick = (group: UserGroup) => {
    setGroupToDelete(group);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!groupToDelete) return;
    try {
      setIsDeleting(true);
      await deleteUserGroup(groupToDelete.id);
      toast.success("User group deleted successfully.");
      setGroups((prev) => prev.filter((g) => g.id !== groupToDelete.id));
    } catch (error) {
      const axiosError = error as AxiosError<{ error?: string }>;
      toast.error(axiosError.response?.data?.error ?? "Failed to delete user group.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setGroupToDelete(null);
    }
  };

  const filteredGroups = groups.filter((g) =>
    g.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const columns: Column<UserGroup>[] = [
    { header: "#", key: "index", cell: (_group, index) => index + 1 },
    {
      header: "Name",
      key: "name",
      cell: (group) => group.name,
      className: "font-medium",
    },
    {
      header: "Description",
      key: "description",
      cell: (group) => group.description ?? "—",
      className: "text-zinc-500",
    },
    {
      header: "Created At",
      key: "created_at",
      cell: (group) => formatDate(group.created_at),
      className: "truncate",
    },
    {
      header: "Updated At",
      key: "updated_at",
      cell: (group) => formatDate(group.updated_at),
      className: "truncate",
    },
    {
      header: "Actions",
      key: "actions",
      cell: (group) => (
        <ActionButtons
          canEdit
          canDelete
          onEdit={() => onEditGroup(group)}
          onDelete={() => handleDeleteClick(group)}
          editTitle="Edit Group"
          deleteTitle="Delete Group"
        />
      ),
    },
  ];

  const isSearchActive = searchQuery.trim().length > 0;

  const emptyState = useMemo(
    () => (
      <ListEmptyState
        icon={<UsersRound className="h-12 w-12 text-gray-400" />}
        title={
          isSearchActive
            ? "No matching user groups"
            : "No user groups yet"
        }
        description={
          isSearchActive
            ? "Try adjusting your search query."
            : "Create a group to scope which agents and conversations members can see."
        }
        action={
          !isSearchActive ? (
            <Button
              onClick={onCreateGroup}
              className="rounded-full flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              Add New Group
            </Button>
          ) : undefined
        }
      />
    ),
    [isSearchActive, onCreateGroup]
  );

  return (
    <>
      <DataTable
        data={filteredGroups}
        columns={columns}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        pageSize={LIST_PAGE_SIZE}
        emptyMessage="No user groups found"
        notFoundMessage="No user groups found matching your search"
        emptyState={emptyState}
      />

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isInProgress={isDeleting}
        itemName={groupToDelete?.name ?? ""}
        description={`This action cannot be undone. This will permanently delete the group "${groupToDelete?.name}".`}
      />
    </>
  );
}