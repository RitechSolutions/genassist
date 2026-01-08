import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { UserTypesCard } from "@/views/UserTypes/components/UserTypesCard";
import { UserTypeDialog } from "../components/UserTypeDialog";
import { UserType } from "@/interfaces/userType.interface";

export default function UserTypes() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [userTypeToEdit, setUserTypeToEdit] = useState<UserType | null>(null);
  const [updatedUserType, setUpdatedUserType] = useState<UserType | null>(null);

  const handleUserTypeSaved = () => {
    setRefreshKey(prevKey => prevKey + 1);
  };

  const handleUserTypeUpdated = (userType: UserType) => {
    setUpdatedUserType(userType);
  };

  const handleCreateUserType = () => {
    setDialogMode('create');
    setUserTypeToEdit(null);
    setIsDialogOpen(true);
  };
  
  const handleEditUserType = (userType: UserType) => {
    setDialogMode('edit');
    setUserTypeToEdit(userType);
    setIsDialogOpen(true);
  };

  return (
    <PageLayout>
      <PageHeader
        title="User Types"
        subtitle="View and manage system user types"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search user types..."
        actionButtonText="Add New User Type"
        onActionClick={handleCreateUserType}
      />
      
      <UserTypesCard
        searchQuery={searchQuery}
        refreshKey={refreshKey}
        onEditUserType={handleEditUserType}
        updatedUserType={updatedUserType}
      />

      <UserTypeDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onUserTypeSaved={handleUserTypeSaved}
        onUserTypeUpdated={handleUserTypeUpdated}
        userTypeToEdit={userTypeToEdit}
        mode={dialogMode}
      />
    </PageLayout>
  );
} 