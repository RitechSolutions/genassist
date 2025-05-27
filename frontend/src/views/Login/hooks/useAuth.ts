import { useState } from "react";
import { login as loginApi } from "@/services/auth";
import { AxiosError } from "axios";
import toast from "react-hot-toast";
import { useFeatureFlag } from "@/context/FeatureFlagContext";

export const useAuth = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(
    localStorage.getItem("isAuthenticated") === "true"
  );
  const { refreshFlags } = useFeatureFlag();

  const login = async (username: string, password: string): Promise<boolean> => {
    try {
      const response = await loginApi({ username, password });
      
      if (response) {
        setIsAuthenticated(true);
        refreshFlags();
        return true;
      }
      return false;
    } catch (error) {
      if (error instanceof AxiosError) {
        if (error.response?.status === 422) {
          toast.error("Invalid username or password");
        } else if (error.response?.status === 401) {
          toast.error("Unauthorized access");
        } else {
          toast.error("An error occurred during login");
          console.error("Login error:", error.response?.data);
        }
      } else {
        console.error("Login error:", error);
      }
      return false;
    }
  };

  const logout = () => {
    localStorage.removeItem("isAuthenticated");
    setIsAuthenticated(false);
  };

  const checkAuth = (): boolean => {
    return localStorage.getItem("isAuthenticated") === "true";
  };

  return {
    isAuthenticated,
    login,
    logout,
    checkAuth
  };
}; 