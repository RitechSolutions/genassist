import { Column } from "@/components/ui/data-table";
import { EntityTableCard } from "@/components/EntityTableCard";
import { Badge } from "@/components/badge";
import { getAllRoles, deleteRole } from "@/services/roles";
import { formatDate } from "@/helpers/utils";
import { Role } from "@/interfaces/role.interface";

interface RolesCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditRole: (role: Role) => void;
  updatedRole?: Role | null;
}

// roles that cannot be edited
const restrictedRoles = new Set(["admin", "superadmin"]);

export function RolesCard({
  searchQuery,
  refreshKey = 0,
  onEditRole,
  updatedRole = null,
}: RolesCardProps) {
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
  ];

  return (
    <EntityTableCard<Role>
      entityName="role"
      searchQuery={searchQuery}
      searchFields={["name"]}
      refreshKey={refreshKey}
      updatedItem={updatedRole}
      fetchFn={getAllRoles}
      deleteFn={(role) => deleteRole(role.id)}
      getItemName={(role) => role.name}
      deleteDescription={(role) =>
        `This action cannot be undone. This will permanently delete the role "${role.name}".`
      }
      emptyMessage="No roles found"
      notFoundMessage="No roles found matching your search"
      columns={columns}
      rowActions={{
        onEdit: onEditRole,
        editTitle: "Edit Role",
        deleteTitle: "Delete Role",
        canEdit: (role) => !restrictedRoles.has(role.name),
        canDelete: (role) => !restrictedRoles.has(role.name),
      }}
    />
  );
}
