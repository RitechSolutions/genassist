import type { User } from "@/interfaces/user.interface";

/** Supervision only counts while the user still holds the supervisor role. */
export function isSupervisorUser(user: Pick<User, "roles">): boolean {
  return !!user.roles?.some((role) => role.name?.toLowerCase() === "supervisor");
}

/** Supervised groups a user actively holds, excluding their own group. */
export function activeSupervisedGroupIds(
  user: Pick<User, "roles" | "supervised_group_ids" | "group_id">,
): string[] {
  if (!isSupervisorUser(user)) return [];
  return (user.supervised_group_ids ?? []).filter((id) => id && id !== user.group_id);
}
