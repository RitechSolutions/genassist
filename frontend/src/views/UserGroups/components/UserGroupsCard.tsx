import { useEffect, useMemo, useState } from "react";
import { AxiosError } from "axios";
import { DataTable } from "@/components/DataTable";
import { ListEmptyState } from "@/components/ListEmptyState";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { TableCell, TableRow } from "@/components/table";
import { Button } from "@/components/button";
import { getAllUserGroups, deleteUserGroup } from "@/services/userGroups";
import { formatDate } from "@/helpers/utils";
import { UserGroup } from "@/interfaces/userGroup.interface";
import { toast } from "react-hot-toast";
import { getPaginationMeta } from "@/helpers/pagination";
import { PaginationBar } from "@/components/PaginationBar";
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
  const PAGE_SIZE = 10;
  const [groups, setGroups] = useState<UserGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [groupToDelete, setGroupToDelete] = useState<UserGroup | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);

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

  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

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

  const pagination = getPaginationMeta(filteredGroups.length, PAGE_SIZE, currentPage);
  const paginatedGroups = filteredGroups.slice(pagination.startIndex, pagination.endIndex);

  const headers = ["#", "Name", "Description", "Created At", "Updated At", "Actions"];

  const renderRow = (group: UserGroup, index: number) => (
    <TableRow key={group.id}>
      <TableCell>{pagination.startIndex + index + 1}</TableCell>
      <TableCell className="font-medium">{group.name}</TableCell>
      <TableCell className="text-zinc-500">{group.description ?? "—"}</TableCell>
      <TableCell className="truncate">{formatDate(group.created_at)}</TableCell>
      <TableCell className="truncate">{formatDate(group.updated_at)}</TableCell>
      <TableCell>
        <ActionButtons
          canEdit
          canDelete
          onEdit={() => onEditGroup(group)}
          onDelete={() => handleDeleteClick(group)}
          editTitle="Edit Group"
          deleteTitle="Delete Group"
        />
      </TableCell>
    </TableRow>
  );

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
        data={paginatedGroups}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        headers={headers}
        renderRow={renderRow}
        emptyMessage="No user groups found"
        searchEmptyMessage="No user groups found matching your search"
        emptyState={emptyState}
      />

      <PaginationBar
        total={pagination.total}
        pageSize={PAGE_SIZE}
        currentPage={pagination.safePage}
        pageItemCount={paginatedGroups.length}
        onPageChange={setCurrentPage}
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