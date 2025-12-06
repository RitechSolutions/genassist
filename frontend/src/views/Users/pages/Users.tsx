import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { UsersCard } from "@/views/Users/components/UsersCard";
import { UserDialog } from "../components/UserDialog";
import { User } from "@/interfaces/user.interface";

export default function Users() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [userToEdit, setUserToEdit] = useState<User | null>(null);
  const [updatedUser, setUpdatedUser] = useState<User | null>(null);

  const handleUserSaved = () => {
    setRefreshKey((prevKey) => prevKey + 1);
  };

  const handleUserUpdated = (user: User) => {
    setUpdatedUser(user);
  };

  const handleCreateUser = () => {
    setDialogMode("create");
    setUserToEdit(null);
    setIsDialogOpen(true);
  };

  const handleEditUser = (user: User) => {
    setDialogMode("edit");
    setUserToEdit(user);
    setIsDialogOpen(true);
  };

  return (
    <PageLayout>
      <PageHeader
        title="Users"
        subtitle="View and manage system users"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search users..."
        actionButtonText="Add New User"
        onActionClick={handleCreateUser}
      />

      <UsersCard
        searchQuery={searchQuery}
        refreshKey={refreshKey}
        onEditUser={handleEditUser}
        updatedUser={updatedUser}
      />

      <UserDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onUserCreated={handleUserSaved}
        onUserUpdated={handleUserUpdated}
        userToEdit={userToEdit}
        mode={dialogMode}
      />
    </PageLayout>
  );
}
