import { useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { UserGroupsCard } from "@/views/UserGroups/components/UserGroupsCard";
import { UserGroupDialog } from "@/views/UserGroups/components/UserGroupDialog";
import { UserGroup } from "@/interfaces/userGroup.interface";
import { Info } from "lucide-react";

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

      <div className="flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <span>
          Group-based row filtering is currently applied to: <strong>Agent Studio</strong>.
          Members of a group can only see resources created by users in the same group.
          Supervisors assigned to a group can see resources from all groups they supervise.
        </span>
      </div>

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