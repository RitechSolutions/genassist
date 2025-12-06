import { apiRequest } from "@/config/api";
import {
  Webhook,
  WebhookCreatePayload,
  WebhookUpdatePayload,
} from "@/interfaces/webhook.interface";

const BASE = "webhooks";

export const getAllWebhooks = async (): Promise<Webhook[]> => {
  try {
    const data = await apiRequest<Webhook[]>("GET", `${BASE}`);
    if (!data || !Array.isArray(data)) {
      return [];
    }
    return data;
  } catch (error) {
    throw error;
  }
};

export const getWebhook = async (id: string): Promise<Webhook | null> => {
  try {
    const data = await apiRequest<Webhook>("GET", `${BASE}/${id}`);
    return data ?? null;
  } catch (error) {
    throw error;
  }
};

export const createWebhook = async (
  webhookData: WebhookCreatePayload
): Promise<Webhook> => {
  try {
    const response = await apiRequest<Webhook>("POST", `${BASE}`, webhookData as unknown as Record<string, unknown>);
    if (!response) throw new Error("Failed to create webhook");
    return response;
  } catch (error) {
    throw error;
  }
};

export const updateWebhook = async (
  id: string,
  webhookData: WebhookUpdatePayload
): Promise<Webhook> => {
  try {
    const response = await apiRequest<Webhook>("PUT", `${BASE}/${id}`, webhookData as unknown as Record<string, unknown>);
    if (!response) throw new Error("Failed to update webhook");
    return response;
  } catch (error) {
    throw error;
  }
};

export const deleteWebhook = async (id: string): Promise<void> => {
  try {
    await apiRequest("DELETE", `${BASE}/${id}`);
  } catch (error) {
    throw error;
  }
};

export const executeWebhook = async (
  id: string,
  payload: any,
  method: "POST" | "GET" = "POST"
): Promise<any> => {
  try {
    const url = `${BASE}/${id}/execute-workflow`;
    if (method === "POST") {
      return await apiRequest("POST", url, payload);
    } else {
      return await apiRequest("GET", url, payload);
    }
  } catch (error) {
    throw error;
  }
};
