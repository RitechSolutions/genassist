import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { RolesCard } from "@/views/Roles/components/RolesCard";
import { RoleDialog } from "@/views/Roles/components/RoleDialog";
import { Role } from "@/interfaces/role.interface";

export default function Roles() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [roleToEdit, setRoleToEdit] = useState<Role | null>(null);
  const [updatedRole, setUpdatedRole] = useState<Role | null>(null);

  const handleRoleSaved = () => {
    setRefreshKey(prevKey => prevKey + 1);
  };

  const handleRoleUpdated = (role: Role) => {
    setUpdatedRole(role);
  };

  const handleCreateRole = () => {
    setDialogMode('create');
    setRoleToEdit(null);
    setIsDialogOpen(true);
  };
  
  const handleEditRole = (role: Role) => {
    setDialogMode('edit');
    setRoleToEdit(role);
    setIsDialogOpen(true);
  };

  return (
    <PageLayout>
      <PageHeader
        title="Roles"
        subtitle="View and manage system roles"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search roles..."
        actionButtonText="Add New Role"
        onActionClick={handleCreateRole}
      />
      
      <RolesCard
        searchQuery={searchQuery}
        refreshKey={refreshKey}
        onEditRole={handleEditRole}
        updatedRole={updatedRole}
      />

      <RoleDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onRoleSaved={handleRoleSaved}
        onRoleUpdated={handleRoleUpdated}
        roleToEdit={roleToEdit}
        mode={dialogMode}
      />
    </PageLayout>
  );
} 