import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { UserGroupsCard } from "@/views/UserGroups/components/UserGroupsCard";
import { UserGroupDialog } from "@/views/UserGroups/components/UserGroupDialog";
import { UserGroup } from "@/interfaces/userGroup.interface";

export default function UserGroups() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [groupToEdit, setGroupToEdit] = useState<UserGroup | null>(null);
  const [updatedGroup, setUpdatedGroup] = useState<UserGroup | null>(null);

  const handleGroupSaved = () => {
    setRefreshKey((prev) => prev + 1);
  };

  const handleGroupUpdated = (group: UserGroup) => {
    setUpdatedGroup(group);
  };

  const handleCreateGroup = () => {
    setDialogMode("create");
    setGroupToEdit(null);
    setIsDialogOpen(true);
  };

  const handleEditGroup = (group: UserGroup) => {
    setDialogMode("edit");
    setGroupToEdit(group);
    setIsDialogOpen(true);
  };

  return (
    <PageLayout>
      <PageHeader
        title="User Groups"
        subtitle="View and manage user groups"
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search groups..."
        actionButtonText="Add New Group"
        onActionClick={handleCreateGroup}
      />

      <UserGroupsCard
        searchQuery={searchQuery}
        refreshKey={refreshKey}
        onEditGroup={handleEditGroup}
        updatedGroup={updatedGroup}
      />

      <UserGroupDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onGroupSaved={handleGroupSaved}
        onGroupUpdated={handleGroupUpdated}
        groupToEdit={groupToEdit}
        mode={dialogMode}
      />
    </PageLayout>
  );
}