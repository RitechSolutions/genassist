import { apiRequest } from "@/config/api";
import {
  CreateTemplateFromAgentPayload,
  InstallTemplateResponse,
  Template,
  TemplateListItem,
} from "@/interfaces/template.interface";

const BASE = "genagent/templates";

export const getTemplates = async (): Promise<TemplateListItem[]> => {
  const data = await apiRequest<TemplateListItem[]>("GET", BASE);
  return Array.isArray(data) ? data : [];
};

export const getTemplate = async (id: string): Promise<Template | null> => {
  return apiRequest<Template>("GET", `${BASE}/${id}`);
};

export const installTemplate = async (
  id: string,
  name?: string
): Promise<InstallTemplateResponse> => {
  const res = await apiRequest<InstallTemplateResponse>(
    "POST",
    `${BASE}/${id}/install`,
    { name: name ?? null }
  );
  if (!res) throw new Error("Failed to install template");
  return res;
};

export const createTemplateFromAgent = async (
  payload: CreateTemplateFromAgentPayload
): Promise<Template> => {
  const res = await apiRequest<Template>(
    "POST",
    `${BASE}/from-agent`,
    payload as unknown as Record<string, unknown>
  );
  if (!res) throw new Error("Failed to save template");
  return res;
};

export const deleteTemplate = async (id: string): Promise<void> => {
  await apiRequest("DELETE", `${BASE}/${id}`);
};

export const publishTemplate = async (id: string): Promise<Template> => {
  const res = await apiRequest<Template>("POST", `${BASE}/${id}/publish`);
  if (!res) throw new Error("Failed to publish template");
  return res;
};

export const getReviewQueue = async (): Promise<TemplateListItem[]> => {
  const data = await apiRequest<TemplateListItem[]>("GET", `${BASE}/review`);
  return Array.isArray(data) ? data : [];
};

export const approveTemplate = async (id: string): Promise<void> => {
  await apiRequest("POST", `${BASE}/review/${id}/approve`);
};

export const rejectTemplate = async (
  id: string,
  reason?: string
): Promise<void> => {
  await apiRequest("POST", `${BASE}/review/${id}/reject`, {
    reason: reason ?? null,
  });
};

/** Withdraw the caller's published copy of their own template (by private id). */
export const unpublishTemplate = async (id: string): Promise<void> => {
  await apiRequest("POST", `${BASE}/${id}/unpublish`);
};

/** Master-admin removal of a published/community template (by master id). */
export const removeGlobalTemplate = async (id: string): Promise<void> => {
  await apiRequest("DELETE", `${BASE}/review/${id}`);
};
