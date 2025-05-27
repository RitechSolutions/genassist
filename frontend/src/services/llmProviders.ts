import { apiRequest } from "@/config/api";
import { LLMProvider } from "@/interfaces/llmProvider.interface";

export const getAllLLMProviders = async (): Promise<LLMProvider[]> => {
  try {
    return await apiRequest<LLMProvider[]>("GET", "llm-providers/");
  } catch (error) {
    console.error("Error fetching LLM providers:", error);
    throw error;
  }
};

export const getLLMProvider = async (
  id: string
): Promise<LLMProvider | null> => {
  try {
    return await apiRequest<LLMProvider>("GET", `llm-providers/${id}`);
  } catch (error) {
    console.error("Error fetching LLM provider:", error);
    throw error;
  }
};

export const createLLMProvider = async (
  providerData: Omit<LLMProvider, "id" | "created_at" | "updated_at">
): Promise<LLMProvider> => {
  try {
    return await apiRequest<LLMProvider>(
      "POST",
      "llm-providers",
      JSON.parse(JSON.stringify(providerData))
    );
  } catch (error) {
    console.error("Error creating LLM provider:", error);
    throw error;
  }
};

export const updateLLMProvider = async (
  id: string,
  providerData: Partial<Omit<LLMProvider, "id" | "created_at" | "updated_at">>
): Promise<LLMProvider> => {
  try {
    return await apiRequest<LLMProvider>(
      "PATCH",
      `llm-providers/${id}`,
      JSON.parse(JSON.stringify(providerData))
    );
  } catch (error) {
    console.error("Error updating LLM provider:", error);
    throw error;
  }
};

export const deleteLLMProvider = async (id: string): Promise<void> => {
  try {
    await apiRequest<void>("DELETE", `llm-providers/${id}`);
  } catch (error) {
    console.error("Error deleting LLM provider:", error);
    throw error;
  }
};
