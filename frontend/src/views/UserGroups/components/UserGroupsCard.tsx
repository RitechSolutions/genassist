import { Column } from "@/components/ui/data-table";
import { EntityTableCard } from "@/components/EntityTableCard";
import { Button } from "@/components/button";
import { getAllUserGroups, deleteUserGroup } from "@/services/userGroups";
import { formatDate } from "@/helpers/utils";
import { UserGroup } from "@/interfaces/userGroup.interface";
import { UsersRound, Plus } from "lucide-react";

interface UserGroupsCardProps {
  searchQuery: string;
  refreshKey?: number;
  onEditGroup: (group: UserGroup) => void;
  updatedGroup?: UserGroup | null;
  onCreateGroup: () => void;
}

export function UserGroupsCard({
  searchQuery,
  refreshKey = 0,
  onEditGroup,
  updatedGroup = null,
  onCreateGroup,
}: UserGroupsCardProps) {
  const columns: Column<UserGroup>[] = [
    { header: "#", key: "index", cell: (_group, index) => index + 1 },
    {
      header: "Name",
      key: "name",
      cell: (group) => group.name,
      className: "font-medium",
    },
    {
      header: "Description",
      key: "description",
      cell: (group) => group.description ?? "—",
      className: "text-muted-foreground",
    },
    {
      header: "Created At",
      key: "created_at",
      cell: (group) => formatDate(group.created_at),
      className: "truncate",
    },
    {
      header: "Updated At",
      key: "updated_at",
      cell: (group) => formatDate(group.updated_at),
      className: "truncate",
    },
  ];

  return (
    <EntityTableCard<UserGroup>
      entityName="user group"
      searchQuery={searchQuery}
      searchFields={["name"]}
      refreshKey={refreshKey}
      updatedItem={updatedGroup}
      fetchFn={getAllUserGroups}
      deleteFn={(group) => deleteUserGroup(group.id)}
      getItemName={(group) => group.name}
      deleteDescription={(group) =>
        `This action cannot be undone. This will permanently delete the group "${group.name}".`
      }
      emptyMessage="No user groups found"
      notFoundMessage="No user groups found matching your search"
      emptyState={{
        icon: <UsersRound className="h-12 w-12 text-muted-foreground" />,
        title: "No user groups yet",
        searchTitle: "No matching user groups",
        description:
          "Create a group to scope which agents and conversations members can see.",
        searchDescription: "Try adjusting your search query.",
        action: (
          <Button
            onClick={onCreateGroup}
            className="rounded-full flex items-center gap-2"
          >
            <Plus className="h-4 w-4" />
            Add New Group
          </Button>
        ),
      }}
      columns={columns}
      rowActions={{
        onEdit: onEditGroup,
        editTitle: "Edit Group",
        deleteTitle: "Delete Group",
      }}
    />
  );
}