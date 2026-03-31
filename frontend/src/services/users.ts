import { apiRequest } from "@/config/api";
import { Role } from "@/interfaces/role.interface";
import { User } from "@/interfaces/user.interface";
import { UserType } from "@/interfaces/userType.interface";

export const getAllUsers = async (options?: {
  deletedOnly?: boolean;
}): Promise<User[]> => {
  try {
    const path =
      options?.deletedOnly === true
        ? "user/?deleted_only=true"
        : "user/";
    const data = await apiRequest<User[]>("GET", path);
    return data || [];
  } catch (error) {
    throw error;
  }
};

export const getUser = async (id: string): Promise<User | null> => {
  try {
    return await apiRequest<User>("GET", `user/${id}`);
  } catch (error) {
    throw error;
  }
};

export const createUser = async (userData: User): Promise<User> => {
  try {
    const requestData = {
      username: userData.username,
      email: userData.email,
      password: userData.password,
      is_active: userData.is_active,
      user_type_id: userData.user_type_id,
      role_ids: userData.role_ids
    };
    
    const response = await apiRequest<User>("POST", "user", requestData);
    if (!response) throw new Error("Failed to create user");
    return response;
  } catch (error) {
    throw error;
  }
};

export const updateUser = async (id: string, userData: Partial<User>): Promise<User> => {
  try {
    const response = await apiRequest<User>("PUT", `user/${id}`, userData);
    if (!response) throw new Error("Failed to update user");
    return response;
  } catch (error) {
    throw error;
  }
};

export const deleteUser = async (id: string): Promise<void> => {
  try {
    await apiRequest("DELETE", `user/${id}`);
  } catch (error) {
    throw error;
  }
};

export const restoreUser = async (id: string): Promise<User> => {
  try {
    const response = await apiRequest<User>("POST", `user/${id}/restore`);
    if (!response) throw new Error("Failed to restore user");
    return response;
  } catch (error) {
    throw error;
  }
};
