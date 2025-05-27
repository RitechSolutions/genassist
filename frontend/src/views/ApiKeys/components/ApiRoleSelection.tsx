import { Label } from "@/components/label";
import { Skeleton } from "@/components/skeleton";

interface ApiRoleSelectionProps {
  availableRoles: { id: string; name: string }[];
  selectedRoles: string[];
  toggleRole: (roleId: string) => void;
  isLoading: boolean;
}

export function ApiRoleSelection({
  availableRoles,
  selectedRoles,
  toggleRole,
  isLoading,
}: ApiRoleSelectionProps) {
  const renderLoadingSkeletons = () =>
    Array.from({ length: 5 }).map((_, index) => (
      <div key={index} className="flex items-center space-x-2">
        <Skeleton className="h-4 w-4 rounded-sm" />
        <Skeleton className="h-4 w-[150px]" />
        <Skeleton className="h-4 w-4 rounded-sm" />
        <Skeleton className="h-4 w-[150px]" />
      </div>
    ));

  const renderNoAvailableRoles = () => (
    <div className="text-sm text-muted-foreground">
      No roles available for your account.
    </div>
  );

  const renderAvailableRoles = () =>
    availableRoles.map((role) => (
      <div key={role.id} className="flex items-center space-x-2">
        <input
          type="checkbox"
          id={`role-${role.id}`}
          checked={selectedRoles.includes(role.id)}
          onChange={() => toggleRole(role.id)}
          className="form-checkbox h-4 w-4"
          disabled={isLoading}
        />
        <Label
          htmlFor={`role-${role.id}`}
          className="text-sm font-normal cursor-pointer"
        >
          {role.name}
        </Label>
      </div>
    ));

  return (
    <div className="space-y-2">
      <Label>Roles</Label>
      <div className="border rounded-md p-4 space-y-2 max-h-60 overflow-y-auto">
        {isLoading
          ? renderLoadingSkeletons()
          : availableRoles.length === 0
          ? renderNoAvailableRoles()
          : renderAvailableRoles()}
      </div>
    </div>
  );
}
