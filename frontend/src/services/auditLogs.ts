import { apiRequest } from "@/config/api";
import { AuditLog } from "@/interfaces/audit-log.interface";
import { User } from "@/interfaces/user.interface";

export const fetchAuditLogs = async (
  date_from: string,
  date_to: string,
  action: string,
  user: string
): Promise<AuditLog[]> => {
  try {
    const queryParams = new URLSearchParams();

    if (date_from) queryParams.append("date_from", date_from);
    if (date_to) queryParams.append("date_to", date_to);
    if (action) queryParams.append("action", action);
    if (user) queryParams.append("user", user);

    const data = await apiRequest<AuditLog[]>(
      "GET",
      `/audit-logs/search?${queryParams.toString()}`
    );

    return data || [];
  } catch (error) {
    throw error;
  }
};

export const fetchAuditLogDetails = async (id: string): Promise<AuditLog> => {
  try {
    const data = await apiRequest<AuditLog[]>("GET", `/audit-logs/search`);
    if (!data || data.length === 0) {
      throw new Error("No audit logs found.");
    }
    const auditLog = data.find((log) => log.id === id);

    if (!auditLog) {
      throw new Error(`No audit log found with ID: ${id}`);
    }
    if (!auditLog.json_changes) {
      throw new Error("No json_changes found in the audit log.");
    }
    return auditLog;
  } catch (error) {
    throw error;
  }
};

export const fetchUsers = async (): Promise<User[]> => {
  try {
    const data = await apiRequest<User[]>("GET", "user/");
    return data || [];
  } catch (error) {
    throw error;
  }
};
