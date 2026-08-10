import { useEffect, useState } from "react";
import { AxiosError } from "axios";
import { DataTable, Column } from "@/components/ui/data-table";
import { LIST_PAGE_SIZE } from "@/constants/pagination";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Badge } from "@/components/badge";
import { getAllRoles, deleteRole } from "@/services/roles";
import { formatDate } from "@/helpers/utils";
import { Role } from "@/interfaces/role.interface";
import { toast } from "react-hot-toast";

interface RolesCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditRole: (role: Role) => void;
  updatedRole?: Role | null;
}

export function RolesCard({
  searchQuery,
  refreshKey = 0,
  onEditRole,
  updatedRole = null,
}: RolesCardProps) {
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [roleToDelete, setRoleToDelete] = useState<Role | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // roles that cannot be edited
  const restrictedRoles = new Set(["admin", "superadmin"]);

  useEffect(() => {
    fetchRoles();
  }, [refreshKey]);

  useEffect(() => {
    if (updatedRole) {
      setRoles((prevRoles) =>
        prevRoles.map((role) =>
          role.id === updatedRole.id ? updatedRole : role
        )
      );
    }
  }, [updatedRole]);

  const fetchRoles = async () => {
    try {
      setLoading(true);
      const data = await getAllRoles();
      setRoles(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch roles");
      toast.error("Failed to fetch roles.");
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
      toast.success("Role deleted successfully.");
      setRoles((prev) => prev.filter((s) => s.id !== roleToDelete.id));
    } catch (error) {
      const axiosError = error as AxiosError<{ error?: string }>;
      const apiMessage = axiosError.response?.data?.error;
      toast.error(apiMessage ?? "Failed to delete role.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setRoleToDelete(null);
    }
  };

  const filteredRoles = roles.filter((role) =>
    role.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const columns: Column<Role>[] = [
    { header: "ID", key: "id", cell: (_role, index) => index + 1 },
    {
      header: "Name",
      key: "name",
      cell: (role) => role.name,
      className: "font-medium break-all",
    },
    {
      header: "Status",
      key: "status",
      className: "overflow-hidden whitespace-nowrap text-clip",
      cell: (role) => (
        <Badge variant={role.is_active === 1 ? "default" : "secondary"}>
          {role.is_active === 1 ? "Active" : "Inactive"}
        </Badge>
      ),
    },
    {
      header: "Created At",
      key: "created_at",
      cell: (role) => formatDate(role.created_at),
      className: "truncate",
    },
    {
      header: "Updated At",
      key: "updated_at",
      cell: (role) => formatDate(role.updated_at),
      className: "truncate",
    },
    {
      header: "Actions",
      key: "actions",
      cell: (role) => (
        <ActionButtons
          canEdit={!restrictedRoles.has(role.name)}
          canDelete={!restrictedRoles.has(role.name)}
          onEdit={() => onEditRole(role)}
          onDelete={() => handleDeleteClick(role)}
          editTitle="Edit Role"
          deleteTitle="Delete Role"
        />
      ),
    },
  ];

  return (
    <>
      <DataTable
        data={filteredRoles}
        columns={columns}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        pageSize={LIST_PAGE_SIZE}
        emptyMessage="No roles found"
        notFoundMessage="No roles found matching your search"
      />

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isInProgress={isDeleting}
        itemName={roleToDelete?.name || ""}
        description={`This action cannot be undone. This will permanently delete the role "${roleToDelete?.name}".`}
      />
    </>
  );
}
