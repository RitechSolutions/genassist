import { jwtDecode } from "jwt-decode";
import { apiRequest } from "@/config/api";
import { User } from "@/interfaces/user.interface";
import { Role } from "@/interfaces/role.interface";

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  force_upd_pass_date?: string;
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
  credentials: LoginCredentials,
  tenant?: string
): Promise<AuthTokens> => {
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
          ...(tenant ? { "x-tenant-id": tenant } : {}),
        },
      }
    );

    if (response?.access_token) {
      localStorage.setItem("access_token", response.access_token);
      localStorage.setItem("refresh_token", response.refresh_token);
      localStorage.setItem("tenant_id", tenant ? tenant : "");
      const tokenType = response.token_type || "bearer";
      localStorage.setItem("token_type", tokenType.toLowerCase() === "bearer" ? "Bearer" : tokenType);
      localStorage.setItem("isAuthenticated", "true");
    
    // Store force_upd_pass_date if provided
      if (response.force_upd_pass_date) {
        localStorage.setItem("force_upd_pass_date", response.force_upd_pass_date);
      }
    }

    return response;
  };

export const fetchUserPermissions = async (): Promise<void> => {
  const permissionsResponse = await apiRequest<AuthMeResponse>(
    "GET",
    "/auth/me"
  );
  const userPermissions = permissionsResponse?.permissions || [];
  localStorage.setItem("permissions", JSON.stringify(userPermissions));
};

export const getPermissions = (): string[] => {
  const permissions = localStorage.getItem("permissions");

  if (!permissions) {
    return [];
  }

  try {
    return permissions ? JSON.parse(permissions) : [];
  } catch (error) {
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
  localStorage.removeItem("force_upd_pass_date");
  localStorage.removeItem("tenant_id");
  localStorage.removeItem("auth_username");

  const token = localStorage.getItem("access_token");
  if (token) {
    try {
      apiRequest("POST", "auth/logout", {});
    } catch (error) {
    }
  }
};

export const getAccessToken = (): string | null => {
  return localStorage.getItem("access_token");
};

export const getRefreshToken = (): string | null => {
  return localStorage.getItem("refresh_token");
};

export const getTenantId = (): string | null => {
  return localStorage.getItem("tenant_id");
};

/**
 * Check if a token is expired without any side effects
 */
export const isTokenExpired = (token: string): boolean => {
  try {
    const decoded = jwtDecode<TokenPayload>(token);
    const currentTime = Date.now() / 1000;
    return decoded.exp < currentTime;
  } catch (error) {
    return true; // Consider invalid tokens as expired
  }
};

/**
 * Check if token is valid (exists and not expired) without clearing auth state
 */
export const isTokenValid = (): boolean => {
  const token = getAccessToken();

  if (!token) {
    return false;
  }

  try {
    const decoded = jwtDecode<TokenPayload>(token);
    const currentTime = Date.now() / 1000;

    // Don't call logout() here - let the refresh token logic handle expired tokens
    if (decoded.exp < currentTime) {
      return false;
    }

    return true;
  } catch (error) {
    // Only logout for malformed tokens, not expired ones
    logout();
    return false;
  }
};

/**
 * Check if user is authenticated. This considers both token validity and refresh capability.
 */
export const isAuthenticated = (): boolean => {
  const accessToken = getAccessToken();
  const refreshToken = getRefreshToken();
  
  // No tokens at all means not authenticated
  if (!accessToken && !refreshToken) {
    return false;
  }

  // If we only have a refresh token (no access token), consider authenticated
  // The refresh token will be used to get a new access token
  if (!accessToken && refreshToken) {
    return true;
  }

  // If we have a valid access token, user is authenticated
  if (accessToken && isTokenValid()) {
    return true;
  }

  // If access token is expired but we have a refresh token, 
  // consider user still authenticated (refresh will handle it)
  if (accessToken && refreshToken && isTokenExpired(accessToken)) {
    return true;
  }

  // No refresh token and invalid access token means not authenticated
  return false;
};

export const isPasswordUpdateRequired = (): boolean => {
  const forceUpdPassDate = localStorage.getItem("force_upd_pass_date");
  
  if (!forceUpdPassDate) return false;
  
  try {
    const forceUpdateDate = new Date(forceUpdPassDate);
    const today = new Date();
    today.setHours(23, 59, 59, 999); // End of today
    
    // If force_upd_pass_date is today or in the past, password update is required
    return forceUpdateDate <= today;
  } catch (error) {
    return false;
  }
};

export const getForceUpdatePassDate = (): string | null => {
  return localStorage.getItem("force_upd_pass_date");
};

export async function getAuthMe(): Promise<User> {
  const response = await apiRequest<User>(
    "GET",
    "/auth/me"
  );
  return response;
}
