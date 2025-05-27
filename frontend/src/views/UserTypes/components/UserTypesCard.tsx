import { useEffect, useState } from "react";
import { Card } from "@/components/card";
import { Edit, Loader2, Trash2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import { formatDate } from "@/helpers/utils";
import { UserType } from "@/interfaces/userType.interface";
import { toast } from "react-hot-toast";
import { Button } from "@/components/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/alert-dialog";
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

  if (loading) {
    return (
      <Card className="p-8 flex justify-center items-center">
        <Loader2 className="w-6 h-6 animate-spin" />
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-8">
        <div className="text-center text-red-500">{error}</div>
      </Card>
    );
  }

  if (filteredUserTypes.length === 0) {
    return (
      <Card className="p-8">
        <div className="text-center text-muted-foreground">
          {searchQuery ? "No user types found matching your search" : "No user types found"}
        </div>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Created At</TableHead>
              <TableHead>Updated At</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredUserTypes.map((userType, index) => (
              <TableRow key={userType.id}>
                <TableCell>{index + 1}</TableCell>
                <TableCell className="font-medium">{userType.name}</TableCell>
                <TableCell>{formatDate(userType.created_at)}</TableCell>
                <TableCell>{formatDate(userType.updated_at)}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEditUserType(userType)}
                      title="Edit User Type"
                    >
                      <Edit className="w-4 h-4 text-black" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteClick(userType)}
                      title="Delete User Type"
                    >
                      <Trash2 className="w-4 h-4 text-red-500" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete the user type
              "{userTypeToDelete?.name}".
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
              className="bg-red-600 hover:bg-red-700 focus:ring-red-600"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
} 