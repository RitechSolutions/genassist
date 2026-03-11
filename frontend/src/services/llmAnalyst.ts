import { apiRequest } from "@/config/api";
import { AvailableEnrichment, AvailableNodeType, LLMAnalyst, LLMProvider } from "@/interfaces/llmAnalyst.interface";

export const getAllLLMAnalysts = async (): Promise<LLMAnalyst[]> => {
  try {
    return await apiRequest<LLMAnalyst[]>("GET", "llm-analyst/");
  } catch (error) {
    throw error;
  }
};

export const getLLMAnalyst = async (id: string): Promise<LLMAnalyst | null> => {
  try {
    return await apiRequest<LLMAnalyst>("GET", `llm-analyst/${id}`);
  } catch (error) {
    throw error;
  }
};

export const createLLMAnalyst = async (
  llmAnalystData: LLMAnalyst
): Promise<LLMAnalyst> => {
  try {
    const response = await apiRequest<LLMAnalyst>(
      "POST",
      "llm-analyst",
      JSON.parse(JSON.stringify(llmAnalystData))
    );
    return response;
  } catch (error) {
    throw error;
  }
};

export const updateLLMAnalyst = async (
  id: string,
  llmAnalystData: Partial<LLMAnalyst>
): Promise<LLMAnalyst> => {
  try {
    const response = await apiRequest<LLMAnalyst>(
      "PATCH",
      `llm-analyst/${id}`,
      JSON.parse(JSON.stringify(llmAnalystData))
    );
    return response;
  } catch (error) {
    throw error;
  }
};

export const deleteLLMAnalyst = async (id: string): Promise<void> => {
  try {
    await apiRequest<void>("DELETE", `llm-analyst/${id}`);
  } catch (error) {
    throw error;
  }
};

export const getAllLLMProviders = async (): Promise<LLMProvider[]> => {
  try {
    const response = await apiRequest<LLMProvider[]>("GET", "llm-providers/");
    return response;
  } catch (error) {
    throw error;
  }
};

export const getAvailableEnrichments = async (): Promise<AvailableEnrichment[]> => {
  try {
    return await apiRequest<AvailableEnrichment[]>("GET", "llm-analyst/available-enrichments");
  } catch (error) {
    throw error;
  }
};

export const getAvailableNodeTypes = async (): Promise<AvailableNodeType[]> => {
  try {
    return await apiRequest<AvailableNodeType[]>("GET", "llm-analyst/available-node-types");
  } catch (error) {
    throw error;
  }
};
