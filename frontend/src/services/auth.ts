import { jwtDecode } from "jwt-decode";
import { apiRequest } from "@/config/api";
import { User } from "@/interfaces/user.interface";
import { Role } from "@/interfaces/role.interface";

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

interface TokenPayload {
  exp: number;
  user_id: string;
  jti: string;
  sub: string;
  permissions: string[];
}

export interface AuthMeResponse {
  permissions: string[];
  roles: Role[]
}

interface LoginCredentials extends Record<string, unknown> {
  username: string;
  password: string;
}

export const login = async (
  credentials: LoginCredentials
): Promise<boolean> => {
  try {
    const formData = new URLSearchParams();
    formData.append("username", credentials.username);
    formData.append("password", credentials.password);
    formData.append("grant_type", "password");

    const response = await apiRequest<AuthTokens>(
      "POST",
      "auth/token",
      formData,
      {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          Accept: "application/json",
        },
      }
    );

    if (response?.access_token) {
      localStorage.setItem("access_token", response.access_token);
      localStorage.setItem("refresh_token", response.refresh_token);
      localStorage.setItem("token_type", response.token_type);
      localStorage.setItem("isAuthenticated", "true");


      const permissionsResponse = await apiRequest<AuthMeResponse>(
        "GET",
        "/auth/me"
      );
      const userPermissions = permissionsResponse?.permissions || [];

      localStorage.setItem("permissions", JSON.stringify(userPermissions));

      return true;
    }

    throw new Error("Invalid credentials");
  } catch (error) {
    console.error("Login failed:", error);
    return false;
  }
};

export const getPermissions = (): string[] => {
  const permissions = localStorage.getItem("permissions");

  if (!permissions) {
    return [];
  }

  try {
    return permissions ? JSON.parse(permissions) : [];
  } catch (error) {
    console.error("Error parsing permissions from localStorage", error);
    return [];
  }
};

export const hasPermission = (permission: string): boolean => {
  const permissions = getPermissions() || [];
  return permissions.includes('*') || permissions.includes(permission);
};

export const hasAllPermissions = (requiredPermissions: string[]): boolean => {
  if (!requiredPermissions || requiredPermissions.length === 0) return true;

  const userPermissions = getPermissions();
  return requiredPermissions.every((perm) => userPermissions.includes(perm));
};

export const hasAnyPermission = (requiredPermissions: string[]): boolean => {
  if (!requiredPermissions || requiredPermissions.length === 0) return true;

  const userPermissions = getPermissions();

  if (userPermissions.includes("*")) return true;
  
  return requiredPermissions.some((perm) => userPermissions.includes(perm));
};

export const logout = (): void => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("token_type");
  localStorage.removeItem("isAuthenticated");
  localStorage.removeItem("permissions");

  const token = localStorage.getItem("access_token");
  if (token) {
    try {
      apiRequest("POST", "auth/logout", {});
    } catch (error) {
      console.error("Error during logout:", error);
    }
  }
};

export const getAccessToken = (): string | null => {
  return localStorage.getItem("access_token");
};

export const isTokenValid = (): boolean => {
  const token = getAccessToken();

  if (!token) {
    return false;
  }

  try {
    const decoded = jwtDecode<TokenPayload>(token);
    const currentTime = Date.now() / 1000;

    if (decoded.exp < currentTime) {
      logout();
      return false;
    }

    return true;
  } catch (error) {
    console.error("Invalid token:", error);
    logout();
    return false;
  }
};

export const isAuthenticated = (): boolean => {
  return !!getAccessToken() && isTokenValid();
};

export async function getAuthMe(): Promise<User> {
  const response = await apiRequest<User>(
    "GET",
    "/auth/me"
  );
  return response;
}
