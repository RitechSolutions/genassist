import { apiRequest } from "@/config/api";
import { AuditLog } from "@/interfaces/audit-log.interface";
import { User } from "@/interfaces/user.interface";

export const fetchAuditLogs = async (
  date_from: string,
  date_to: string,
  action: string,
  table_name: string,
  user: string,
  limit: number,
  offset: number
): Promise<AuditLog[]> => {

  const queryParams = new URLSearchParams();

  if (date_from) queryParams.append("date_from", date_from);
  if (date_to) queryParams.append("date_to", date_to);
  if (action) queryParams.append("action", action);
  if (table_name) queryParams.append("table_name", table_name);
  if (user) queryParams.append("user", user);

  queryParams.append("limit",  String(limit));
  queryParams.append("offset", String(offset));

  const data = await apiRequest<AuditLog[]>(
    "GET",
    `/audit-logs/search?${queryParams.toString()}`
  );

  return data || [];

};

export const fetchAuditLogDetails = async (id: string): Promise<AuditLog> => {
  const data = await apiRequest<AuditLog>("GET", `/audit-logs/${id}`);
  if (!data) {
    throw new Error(`No audit log found with ID: ${id}`);
  }
  if (!data.json_changes) {
    throw new Error("No json_changes found in the audit log.");
  }
  return data;
};

export const fetchUsers = async (): Promise<User[]> => {
  const data = await apiRequest<User[]>("GET", "user/");
  return data || [];
};
