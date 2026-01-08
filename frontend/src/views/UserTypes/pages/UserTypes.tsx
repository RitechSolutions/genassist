import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { UserTypesCard } from "@/views/UserTypes/components/UserTypesCard";
import { UserTypeDialog } from "../components/UserTypeDialog";

export default function UserTypes() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleUserTypeSaved = () => {
    setRefreshKey(prevKey => prevKey + 1);
  };

  const handleCreateUserType = () => {
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
      />

      <UserTypeDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onUserTypeSaved={handleUserTypeSaved}
      />
    </PageLayout>
  );
} 