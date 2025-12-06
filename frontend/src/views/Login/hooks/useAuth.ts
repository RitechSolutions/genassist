import { useState } from "react";
import { login as loginApi } from "@/services/auth";
import { AxiosError } from "axios";
import { useFeatureFlag } from "@/context/FeatureFlagContext";

interface LoginResponse {
  access_token?: string;
  refresh_token?: string;
  token_type?: string;
  force_upd_pass_date?: string;
  error_key?: string;
}

export const useAuth = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(
    localStorage.getItem("isAuthenticated") === "true"
  );
  const { refreshFlags } = useFeatureFlag();

  const login = async (
    username: string,
    password: string,
    tenant?: string
  ): Promise<LoginResponse | null> => {
    try {
      const response = await loginApi({ username, password }, tenant);

      if (response?.access_token) {
        setIsAuthenticated(true);
      }

      return response;
    } catch (error) {
      if (error instanceof AxiosError && error.response) {
        const errorData = error.response.data;
        return errorData;
      } else {
        return null;
      }
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
    checkAuth,
  };
};
