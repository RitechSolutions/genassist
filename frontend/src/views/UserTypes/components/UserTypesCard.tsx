import { useEffect, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { TableCell, TableRow } from "@/components/table";
import { formatDate } from "@/helpers/utils";
import { UserType } from "@/interfaces/userType.interface";
import { toast } from "react-hot-toast";
import { deleteUserType, getAllUserTypes } from "@/services/userTypes";

interface UserTypesCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditUserType: (userType: UserType) => void;
  updatedUserType?: UserType | null;
}

export function UserTypesCard({
  searchQuery,
  refreshKey = 0,
  onEditUserType,
  updatedUserType = null,
}: UserTypesCardProps) {
  const [userTypes, setUserTypes] = useState<UserType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userTypeToDelete, setUserTypeToDelete] = useState<UserType | null>(
    null
  );
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    fetchUserTypes();
  }, [refreshKey]);

  useEffect(() => {
    if (updatedUserType) {
      setUserTypes((prevUserTypes) =>
        prevUserTypes.map((userType) =>
          userType.id === updatedUserType.id ? updatedUserType : userType
        )
      );
    }
  }, [updatedUserType]);

  const fetchUserTypes = async () => {
    try {
      setLoading(true);
      const data = await getAllUserTypes();
      setUserTypes(data);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch user types"
      );
      toast.error("Failed to fetch user types.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteClick = (userType: UserType) => {
    setUserTypeToDelete(userType);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!userTypeToDelete) return;

    try {
      setIsDeleting(true);
      await deleteUserType(userTypeToDelete.id);
      toast.success("User type deleted successfully.");
      setUserTypes((prev) => prev.filter((s) => s.id !== userTypeToDelete.id));
    } catch (error) {
      toast.error("Failed to delete user type.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setUserTypeToDelete(null);
    }
  };

  const filteredUserTypes = userTypes.filter((userType) =>
    userType.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const headers = ["ID", "Name", "Created At", "Updated At", "Actions"];

  const renderRow = (userType: UserType, index: number) => (
    <TableRow key={userType.id}>
      <TableCell>{index + 1}</TableCell>
      <TableCell className="font-medium break-all">{userType.name}</TableCell>
      <TableCell className="truncate">
        {formatDate(userType.created_at)}
      </TableCell>
      <TableCell className="truncate">
        {formatDate(userType.updated_at)}
      </TableCell>
      <TableCell>
        <ActionButtons
          onEdit={() => onEditUserType(userType)}
          onDelete={() => handleDeleteClick(userType)}
          editTitle="Edit User Type"
          deleteTitle="Delete User Type"
        />
      </TableCell>
    </TableRow>
  );

  return (
    <>
      <DataTable
        data={filteredUserTypes}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        headers={headers}
        renderRow={renderRow}
        emptyMessage="No user types found"
        searchEmptyMessage="No user types found matching your search"
      />

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isInProgress={isDeleting}
        itemName={userTypeToDelete?.name || ""}
        description={`This action cannot be undone. This will permanently delete the user type "${userTypeToDelete?.name}".`}
      />
    </>
  );
}
