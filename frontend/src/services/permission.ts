import { apiRequest } from "@/config/api";
import { Permission } from "@/interfaces/permission.interface";

/**
 * `apiRequest` resolves with `null` on 403 rather than throwing, so every read
 * here has to reject explicitly. Returning an empty list instead would be
 * indistinguishable from "this role has no permissions", and the role dialog
 * would then save that empty set over the role's real permissions.
 */
function assertLoaded<T>(data: T | null, resource: string): T {
  if (data === null || data === undefined) {
    throw new Error(`You do not have permission to read ${resource}.`);
  }
  return data;
}

export const getAllPermissions = async (): Promise<Permission[]> => {
  const data = await apiRequest<Permission[]>("GET", "/permissions");
  return assertLoaded(data, "permissions");
};

export const getPermissionsByRoleId = async (roleId: string): Promise<string[]> => {
  const data = await apiRequest<string[]>("GET", `/roles/${roleId}/permissions`);
  return assertLoaded(data, "this role's permissions");
};

/**
 * Replaces the role's permissions with `selectedPermissionIds` in one
 * transactional request. Throws on failure so the caller can keep the dialog
 * open — a rejected set leaves the role exactly as it was.
 *
 * A 403 is rethrown rather than swallowed: this endpoint has two distinct ones
 * — "you may not edit role permissions" and "that permission is reserved for
 * the admin role" — and the admin can only act on the second if the server's
 * message survives.
 */
export const saveRolePermissions = async (
  roleId: string,
  selectedPermissionIds: string[]
): Promise<void> => {
  const result = await apiRequest<{ role_id: string }>(
    "PUT",
    `/roles/${roleId}/permissions`,
    { permission_ids: selectedPermissionIds },
    {},
    { rethrowForbidden: true }
  );

  if (result === null || result === undefined) {
    throw new Error("Could not save the role's permissions.");
  }
};
