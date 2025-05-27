import { apiRequest } from "@/config/api";
import { Role } from "@/interfaces/role.interface";

export const getAllRoles = async (): Promise<Role[]> => {
    try {
      const data = await apiRequest<Role[]>("GET", "roles/");
      return data || [];
    } catch (error) {
      console.error("Error fetching roles:", error);
      throw error;
    }
  };
  
  export const getRole = async (id: string): Promise<Role | null> => {
    try {
      return await apiRequest<Role>("GET", `roles/${id}`);
    } catch (error) {
      console.error("Error fetching role:", error);
      throw error;
    }
  };
  
  export const createRole = async (roleData: Partial<Role>): Promise<Role> => {
    try {
      const response = await apiRequest<Role>("POST", "roles", roleData);
      if (!response) throw new Error("Failed to create role");
      return response;
    } catch (error) {
      console.error("Error creating role:", error);
      throw error;
    }
  };
  
  export const deleteRole = async (id: string): Promise<void> => {
    try {
      await apiRequest("DELETE", `roles/${id}`);
    } catch (error) {
      console.error("Error deleting role:", error);
      throw error;
    }
  };
  
  export const updateRole = async (id: string, roleData: Partial<Role>): Promise<Role> => {
    try {
      const response = await apiRequest<Role>("PATCH", `roles/${id}`, roleData);
      if (!response) throw new Error("Failed to update role");
      return response;
    } catch (error) {
      console.error("Error updating role:", error);
      throw error;
    }
  };