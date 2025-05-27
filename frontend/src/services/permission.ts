import { apiRequest } from "@/config/api";
import { Permission } from "@/interfaces/permission.interface";
import toast from "react-hot-toast";

export const getAllPermissions = async (): Promise<Permission[]> => {
  try {
    const data = await apiRequest<Permission[]>("GET", "/permissions/");
    return data || [];
  } catch (error) {
    console.error("Error fetching permissions:", error);
    throw error;
  }
};

export const getRolePermissions = async (roleId: string): Promise<string[]> => {
  try {
    const permissionsData = await apiRequest<{ permissions: string[] }>(
      "GET",
      `/roles/${roleId}`
    );
    return permissionsData.permissions || [];
  } catch (error) {
    console.error("Error fetching role permissions:", error);
    return [];
  }
};

export const getPermissionsByRoleId = async (
  roleId: string
): Promise<string[]> => {
  try {
    const rolePermissions = await apiRequest<
      Array<{ role_id: string; permission_id: string }>
    >("GET", "/role-permissions");

    const permissionIds = rolePermissions
      .filter((rp) => rp.role_id === roleId)
      .map((rp) => rp.permission_id);

    return permissionIds;
  } catch (error) {
    console.error("Error fetching role-permissions:", error);
    return [];
  }
};

export const getRolePermissionLinksByRoleId = async (
  roleId: string
): Promise<{ id: string; permission_id: string }[]> => {
  try {
    const rolePermissions = await apiRequest<
      Array<{ id: string; role_id: string; permission_id: string }>
    >("GET", "/role-permissions");

    return rolePermissions.filter((rp) => rp.role_id === roleId);
  } catch (error) {
    console.error("Error fetching role-permission links:", error);
    return [];
  }
};

export const saveRolePermissions = async (
  roleId: string,
  selectedPermissionIds: string[]
) => {
  try {
    const existingPermissionIds = await getPermissionsByRoleId(roleId);
    const rolePermissionLinks = await getRolePermissionLinksByRoleId(roleId);

    const toAdd = selectedPermissionIds.filter(
      (id) => !existingPermissionIds.includes(id)
    );

    const toDeleteLinks = rolePermissionLinks.filter(
      (link) => !selectedPermissionIds.includes(link.permission_id)
    );

    const addPromises = toAdd.map((permissionId) =>
      apiRequest("POST", "/role-permissions", {
        role_id: roleId,
        permission_id: permissionId,
        is_active: true,
      })
    );

    const deletePromises = toDeleteLinks.map((link) =>
      apiRequest("DELETE", `/role-permissions/${link.id}`)
    );

    await Promise.all([...addPromises, ...deletePromises]);
    
  } catch (error) {
    console.error("Error saving role permissions:", error);
    toast.error("Failed to update role permissions.");
  }
};