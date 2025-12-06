import { useEffect, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { ActionButtons } from "@/components/ActionButtons";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { TableCell, TableRow } from "@/components/table";
import { Badge } from "@/components/badge";
import { getAllRoles, deleteRole } from "@/services/roles";
import { formatDate } from "@/helpers/utils";
import { Role } from "@/interfaces/role.interface";
import { toast } from "react-hot-toast";
import { getPaginationMeta } from "@/helpers/pagination";
import { PaginationBar } from "@/components/PaginationBar";

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
  const PAGE_SIZE = 10;
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [roleToDelete, setRoleToDelete] = useState<Role | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);

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

  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

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
      toast.error("Failed to delete role.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setRoleToDelete(null);
    }
  };

  const filteredRoles = roles.filter((role) =>
    role.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const pagination = getPaginationMeta(filteredRoles.length, PAGE_SIZE, currentPage);
  const paginatedRoles = filteredRoles.slice(pagination.startIndex, pagination.endIndex);
  const pageItemCount = paginatedRoles.length;

  const headers = [
    "ID",
    "Name",
    "Status",
    "Created At",
    "Updated At",
    "Actions",
  ];

  const renderRow = (role: Role, index: number) => (
    <TableRow key={role.id}>
      <TableCell>{pagination.startIndex + index + 1}</TableCell>
      <TableCell className="font-medium break-all">{role.name}</TableCell>
      <TableCell className="overflow-hidden whitespace-nowrap text-clip">
        <Badge variant={role.is_active === 1 ? "default" : "secondary"}>
          {role.is_active === 1 ? "Active" : "Inactive"}
        </Badge>
      </TableCell>
      <TableCell className="truncate">{formatDate(role.created_at)}</TableCell>
      <TableCell className="truncate">{formatDate(role.updated_at)}</TableCell>
      <TableCell>
        <ActionButtons
          onEdit={() => onEditRole(role)}
          onDelete={() => handleDeleteClick(role)}
          editTitle="Edit Role"
          deleteTitle="Delete Role"
        />
      </TableCell>
    </TableRow>
  );

  return (
    <>
      <DataTable
        data={paginatedRoles}
        loading={loading}
        error={error}
        searchQuery={searchQuery}
        headers={headers}
        renderRow={renderRow}
        emptyMessage="No roles found"
        searchEmptyMessage="No roles found matching your search"
      />

      <PaginationBar
        total={pagination.total}
        pageSize={PAGE_SIZE}
        currentPage={pagination.safePage}
        pageItemCount={pageItemCount}
        onPageChange={setCurrentPage}
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
