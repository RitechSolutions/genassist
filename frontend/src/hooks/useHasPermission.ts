import { usePermissions } from "@/context/PermissionContext";
import { userHasPermission } from "@/services/auth";

/** True when the signed-in user may call endpoints guarded by `permission` */
export const useHasPermission = (permission: string): boolean =>
  userHasPermission(usePermissions(), permission);
