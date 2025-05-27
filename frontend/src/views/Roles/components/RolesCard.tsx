import { useEffect, useState } from "react";
import { getAllRoles, deleteRole } from "@/services/roles";
import { DataTable, Column } from "@/components/ui/data-table";
import { Edit, Trash2 } from "lucide-react";
import { formatDate } from "@/helpers/utils";
import { Role } from "@/interfaces/role.interface";
import { toast } from "react-hot-toast";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";

interface RolesCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditRole: (role: Role) => void;
}

export function RolesCard({ 
  searchQuery, 
  refreshKey = 0, 
  onEditRole 
}: RolesCardProps) {
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [roleToDelete, setRoleToDelete] = useState<Role | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    fetchRoles();
  }, [refreshKey]);

  const fetchRoles = async () => {
    try {
      setLoading(true);
      const data = await getAllRoles();
      setRoles(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch roles");
      toast.error("Failed to fetch roles");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteClick = (role: Role) => {
    setRoleToDelete(role);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!roleToDelete) return;
    
    try {
      setIsDeleting(true);
      await deleteRole(roleToDelete.id);
      toast.success("Role deleted successfully");
      fetchRoles();
    } catch (error) {
      toast.error("Failed to delete role");
      console.error("Error deleting role:", error);
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setRoleToDelete(null);
    }
  };

  const columns: Column<Role>[] = [
    { 
      header: "ID", 
      key: "id",
      cell: (_, index) => index + 1
    },
    { 
      header: "Name", 
      key: "name",
      cell: (role) => (
        <span className="font-medium">{role.name}</span>
      )
    },
    { 
      header: "Status", 
      key: "is_active",
      cell: (role) => (
        <Badge variant={role.is_active === 1 ? "default" : "secondary"}>
          {role.is_active === 1 ? "Active" : "Inactive"}
        </Badge>
      )
    },
    { 
      header: "Created At", 
      key: "created_at",
      cell: (role) => formatDate(role.created_at)
    },
    { 
      header: "Updated At", 
      key: "updated_at",
      cell: (role) => formatDate(role.updated_at)
    },
    { 
      header: "Actions", 
      key: "actions",
      cell: (role) => (
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onEditRole(role)}
            title="Edit Role"
          >
            <Edit className="w-4 h-4 text-black" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleDeleteClick(role)}
            title="Delete Role"
          >
            <Trash2 className="w-4 h-4 text-red-500" />
          </Button>
        </div>
      )
    }
  ];

  const filteredRoles = roles.filter((role) =>
    role.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <>
      <DataTable
        data={filteredRoles}
        columns={columns}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        emptyMessage="No roles found"
        notFoundMessage="No roles found matching your search"
      />

      <DeleteConfirmationDialog
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isDeleting={isDeleting}
        itemName={roleToDelete?.name}
        description="This action cannot be undone."
        confirmButtonText="Delete"
        loadingText="Deleting..."
      />
    </>
  );
} 