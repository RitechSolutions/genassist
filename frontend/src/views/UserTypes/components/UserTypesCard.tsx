import { useEffect, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { ActionButtons } from "@/components/ActionButtons";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { TableCell, TableRow } from "@/components/table";
import { formatDate } from "@/helpers/utils";
import { UserType } from "@/interfaces/userType.interface";
import { toast } from "react-hot-toast";
import { deleteUserType, getAllUserTypes } from "@/services/userTypes";

interface UserTypesCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditUserType: (userType: UserType) => void;
}

export function UserTypesCard({ searchQuery, refreshKey = 0, onEditUserType }: UserTypesCardProps) {
  const [userTypes, setUserTypes] = useState<UserType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userTypeToDelete, setUserTypeToDelete] = useState<UserType | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    fetchUserTypes();
  }, [refreshKey]);

  const fetchUserTypes = async () => {
    try {
      setLoading(true);
      const data = await getAllUserTypes();
      setUserTypes(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch user types");
      toast.error("Failed to fetch user types");
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
      toast.success("User type deleted successfully");
      fetchUserTypes();
    } catch (error) {
      toast.error("Failed to delete user type");
      console.error("Error deleting user type:", error);
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
      <TableCell className="font-medium">{userType.name}</TableCell>
      <TableCell>{formatDate(userType.created_at)}</TableCell>
      <TableCell>{formatDate(userType.updated_at)}</TableCell>
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

      <DeleteConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isDeleting={isDeleting}
        itemName={userTypeToDelete?.name || ""}
        description={`This action cannot be undone. This will permanently delete the user type "${userTypeToDelete?.name}".`}
      />
    </>
  );
} 