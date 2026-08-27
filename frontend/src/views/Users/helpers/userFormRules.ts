import type { CRUDDialogMode } from "@/components/ui/crud-dialog";

/**
 * Roles are mandatory everywhere except when editing a canonical `console` user
 */
export const areUserRolesRequired = (
  mode: CRUDDialogMode,
  userTypeName?: string
): boolean => mode === "create" || userTypeName !== "console";
