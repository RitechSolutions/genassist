import { apiRequest } from "@/config/api";
import { UserGroup } from "@/interfaces/userGroup.interface";

export const getAllUserGroups = async (): Promise<UserGroup[]> => {
  const data = await apiRequest<UserGroup[]>("GET", "user-groups/");
  return data || [];
};

export const createUserGroup = async (data: Partial<UserGroup>): Promise<UserGroup> => {
  const response = await apiRequest<UserGroup>("POST", "user-groups/", data);
  if (!response) throw new Error("Failed to create user group");
  return response;
};

export const updateUserGroup = async (id: string, data: Partial<UserGroup>): Promise<UserGroup> => {
  const response = await apiRequest<UserGroup>("PATCH", `user-groups/${id}`, data);
  if (!response) throw new Error("Failed to update user group");
  return response;
};

export const deleteUserGroup = async (id: string): Promise<void> => {
  await apiRequest("DELETE", `user-groups/${id}`);
};

export const addGroupSupervisor = async (groupId: string, userId: string): Promise<void> => {
  await apiRequest("POST", `user-groups/${groupId}/supervisors/${userId}`);
};

export const removeGroupSupervisor = async (groupId: string, userId: string): Promise<void> => {
  await apiRequest("DELETE", `user-groups/${groupId}/supervisors/${userId}`);
};