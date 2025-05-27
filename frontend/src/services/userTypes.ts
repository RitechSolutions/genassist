import { apiRequest } from "@/config/api";
import { UserType } from "@/interfaces/userType.interface";

export const getAllUserTypes = async (): Promise<UserType[]> => {
    try {
      const data = await apiRequest<UserType[]>("GET", "user-type/");
      return data || [];
    } catch (error) {
      console.error("Error fetching user types:", error);
      throw error;
    }
  };
  
  export const getUserType = async (id: string): Promise<UserType | null> => {
    try {
      return await apiRequest<UserType>("GET", `user-type/${id}`);
    } catch (error) {
      console.error("Error fetching user type:", error);
      throw error;
    }
  };
  
  export const createUserType = async (userTypeData: Partial<UserType>): Promise<UserType> => {
    try {
      const response = await apiRequest<UserType>("POST", "user-type", userTypeData);
      if (!response) throw new Error("Failed to create user type");
      return response;
    } catch (error) {
      console.error("Error creating user type:", error);
      throw error;
    }
  };
  
  export const deleteUserType = async (id: string): Promise<void> => {
    try {
      await apiRequest("DELETE", `user-type/${id}`);
    } catch (error) {
      console.error("Error deleting user type:", error);
      throw error;
    }
  };
  
  export const updateUserType = async (id: string, userTypeData: Partial<UserType>): Promise<UserType> => {
    try {
      const response = await apiRequest<UserType>("PATCH", `user-type/${id}`, userTypeData);
      if (!response) throw new Error("Failed to update user type");
      return response;
    } catch (error) {
      console.error("Error updating user type:", error);
      throw error;
    }
  };